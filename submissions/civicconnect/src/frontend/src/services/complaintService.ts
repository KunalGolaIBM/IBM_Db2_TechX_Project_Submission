import {
  collection,
  doc,
  getDoc,
  getDocs,
  setDoc,
  addDoc,
  updateDoc,
  query,
  where,
  orderBy,
  limit,
  serverTimestamp,
  Timestamp
} from 'firebase/firestore';
import { db, handleFirestoreError, OperationType } from '../firebase';
import {
  Complaint,
  ComplaintUpdate,
  Department,
  NotificationItem,
  CitizenFeedback,
  DEFAULT_DEPARTMENTS,
  ComplaintPriority,
  ComplaintStatus
} from '../types';

/**
 * Seed initial departments if none exist in Firestore
 */
export async function seedInitialDepartments(): Promise<Department[]> {
  const deptCol = 'departments';
  try {
    const snapshot = await getDocs(collection(db, deptCol));
    if (snapshot.empty) {
      const created: Department[] = [];
      for (const dept of DEFAULT_DEPARTMENTS) {
        const docRef = doc(collection(db, deptCol));
        const item: Department = {
          ...dept,
          id: docRef.id,
          staffCount: 1
        };
        await setDoc(docRef, item);
        created.push(item);
      }
      return created;
    } else {
      return snapshot.docs.map(d => ({ ...d.data(), id: d.id } as Department));
    }
  } catch (error) {
    handleFirestoreError(error, OperationType.GET, deptCol);
  }
}

/**
 * Fetch all active departments
 */
export async function fetchDepartments(): Promise<Department[]> {
  const deptCol = 'departments';
  try {
    const snapshot = await getDocs(collection(db, deptCol));
    if (snapshot.empty) {
      return await seedInitialDepartments();
    }
    return snapshot.docs.map(d => ({ ...d.data(), id: d.id } as Department));
  } catch (error) {
    handleFirestoreError(error, OperationType.GET, deptCol);
  }
}

/**
 * Add or update department (Admin only)
 */
export async function saveDepartment(deptData: Partial<Department> & { name: string }): Promise<Department> {
  const deptCol = 'departments';
  try {
    if (deptData.id) {
      const ref = doc(db, deptCol, deptData.id);
      await updateDoc(ref, {
        name: deptData.name,
        description: deptData.description || '',
        active: deptData.active ?? true,
        suggestedCategories: deptData.suggestedCategories || []
      });
      return { ...deptData } as Department;
    } else {
      const ref = doc(collection(db, deptCol));
      const code = 'DEPT-' + deptData.name.replace(/[^a-zA-Z]/g, '').slice(0, 4).toUpperCase();
      const newDept: Department = {
        id: ref.id,
        departmentId: deptData.departmentId || code,
        name: deptData.name,
        description: deptData.description || '',
        active: deptData.active ?? true,
        staffCount: 1,
        suggestedCategories: deptData.suggestedCategories || []
      };
      await setDoc(ref, newDept);
      return newDept;
    }
  } catch (error) {
    handleFirestoreError(error, OperationType.WRITE, deptCol);
  }
}

/**
 * Generate a sequential, collision-free complaint ID like CCMS-2026-0001
 */
export async function generateComplaintId(): Promise<string> {
  const compCol = 'complaints';
  const currentYear = new Date().getFullYear();
  try {
    const q = query(
      collection(db, compCol),
      orderBy('createdAt', 'desc'),
      limit(20)
    );
    const snapshot = await getDocs(q);
    let nextNum = snapshot.size + 1;

    // Check existing IDs to avoid collision
    const existingIds = new Set(snapshot.docs.map(d => d.data().complaintId as string));
    let candidate = `CCMS-${currentYear}-${String(nextNum).padStart(4, '0')}`;
    while (existingIds.has(candidate)) {
      nextNum++;
      candidate = `CCMS-${currentYear}-${String(nextNum).padStart(4, '0')}`;
    }
    return candidate;
  } catch (error) {
    // If index or query fails, generate unique fallback with timestamp
    const randomSuffix = Math.floor(1000 + Math.random() * 9000);
    return `CCMS-${currentYear}-${randomSuffix}`;
  }
}

/**
 * Submit a new complaint by a citizen
 */
export async function submitComplaint(params: {
  userId: string;
  citizenName: string;
  citizenEmail: string;
  title: string;
  description: string;
  category: string;
  location: string;
  landmark?: string;
  imageUrl?: string;
  priority?: ComplaintPriority;
  aiSummary?: string;
  aiKeywords?: string[];
}): Promise<Complaint> {
  const compCol = 'complaints';
  const uniqueId = await generateComplaintId();
  const now = new Date().toISOString();

  // Determine default suggested department
  const matchingCategory = DEFAULT_DEPARTMENTS.find(d =>
    d.suggestedCategories?.includes(params.category)
  );

  const newDocRef = doc(collection(db, compCol));
  const complaintData: Complaint = {
    id: newDocRef.id,
    complaintId: uniqueId,
    userId: params.userId,
    citizenName: params.citizenName || 'Citizen',
    citizenEmail: params.citizenEmail || '',
    title: params.title.trim(),
    description: params.description.trim(),
    category: params.category,
    departmentId: matchingCategory ? matchingCategory.departmentId : undefined,
    departmentName: matchingCategory ? matchingCategory.name : undefined,
    location: params.location.trim(),
    landmark: params.landmark?.trim() || '',
    imageUrl: params.imageUrl || '',
    priority: params.priority || 'medium',
    status: 'Submitted',
    aiSummary: params.aiSummary || '',
    aiKeywords: params.aiKeywords || [],
    createdAt: now,
    updatedAt: now
  };

  try {
    await setDoc(newDocRef, complaintData);

    // Initial audit history record
    await addDoc(collection(db, 'complaintUpdates'), {
      complaintId: uniqueId,
      previousStatus: 'None',
      newStatus: 'Submitted',
      updatedBy: params.citizenName || 'Citizen',
      updatedByUid: params.userId,
      role: 'citizen',
      note: 'Complaint registered by citizen with evidence and location details.',
      timestamp: now
    });

    // In-app notification for citizen
    await addDoc(collection(db, 'notifications'), {
      userId: params.userId,
      title: 'Complaint Registered Successfully',
      message: `Your complaint (${uniqueId}) has been registered and is pending administrative review.`,
      complaintId: uniqueId,
      read: false,
      createdAt: now
    });

    return complaintData;
  } catch (error) {
    handleFirestoreError(error, OperationType.CREATE, compCol);
  }
}

/**
 * Fetch all complaints (Admin/Staff view or public stats)
 */
export async function fetchAllComplaints(): Promise<Complaint[]> {
  const compCol = 'complaints';
  try {
    const q = query(collection(db, compCol), orderBy('createdAt', 'desc'));
    const snapshot = await getDocs(q);
    return snapshot.docs.map(d => ({ ...d.data(), id: d.id } as Complaint));
  } catch (error) {
    handleFirestoreError(error, OperationType.LIST, compCol);
  }
}

/**
 * Fetch complaints belonging to a specific citizen
 */
export async function fetchCitizenComplaints(userId: string): Promise<Complaint[]> {
  const compCol = 'complaints';
  try {
    const q = query(
      collection(db, compCol),
      where('userId', '==', userId),
      orderBy('createdAt', 'desc')
    );
    const snapshot = await getDocs(q);
    return snapshot.docs.map(d => ({ ...d.data(), id: d.id } as Complaint));
  } catch (error) {
    // If composite index is pending, fallback to filtering client-side
    try {
      const qSimple = query(collection(db, compCol), where('userId', '==', userId));
      const snap = await getDocs(qSimple);
      const items = snap.docs.map(d => ({ ...d.data(), id: d.id } as Complaint));
      return items.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    } catch (err2) {
      handleFirestoreError(error, OperationType.GET, compCol);
    }
  }
}

/**
 * Fetch complaints assigned to a department
 */
export async function fetchDepartmentComplaints(departmentName: string): Promise<Complaint[]> {
  const compCol = 'complaints';
  try {
    const q = query(
      collection(db, compCol),
      where('departmentName', '==', departmentName)
    );
    const snapshot = await getDocs(q);
    const items = snapshot.docs.map(d => ({ ...d.data(), id: d.id } as Complaint));
    return items.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  } catch (error) {
    handleFirestoreError(error, OperationType.GET, compCol);
  }
}

/**
 * Fetch timeline update history for a complaint
 */
export async function fetchComplaintUpdates(complaintId: string): Promise<ComplaintUpdate[]> {
  const updateCol = 'complaintUpdates';
  try {
    const q = query(
      collection(db, updateCol),
      where('complaintId', '==', complaintId)
    );
    const snapshot = await getDocs(q);
    const updates = snapshot.docs.map(d => ({ ...d.data(), id: d.id } as ComplaintUpdate));
    return updates.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  } catch (error) {
    handleFirestoreError(error, OperationType.GET, updateCol);
  }
}

/**
 * Assign complaint to department and update priority (Admin action)
 */
export async function assignComplaint(params: {
  complaintDocId: string;
  complaintId: string;
  citizenUserId: string;
  departmentId: string;
  departmentName: string;
  priority: ComplaintPriority;
  adminName: string;
  adminUid: string;
  notes?: string;
}): Promise<void> {
  const compCol = 'complaints';
  const now = new Date().toISOString();
  try {
    const ref = doc(db, compCol, params.complaintDocId);
    await updateDoc(ref, {
      departmentId: params.departmentId,
      departmentName: params.departmentName,
      priority: params.priority,
      status: 'Assigned',
      updatedAt: now
    });

    // History record
    await addDoc(collection(db, 'complaintUpdates'), {
      complaintId: params.complaintId,
      previousStatus: 'Under Review',
      newStatus: 'Assigned',
      updatedBy: params.adminName,
      updatedByUid: params.adminUid,
      role: 'admin',
      note: params.notes || `Assigned to ${params.departmentName} with ${params.priority} priority.`,
      timestamp: now
    });

    // Notification for citizen
    await addDoc(collection(db, 'notifications'), {
      userId: params.citizenUserId,
      title: 'Complaint Assigned to Department',
      message: `Your complaint ${params.complaintId} has been assigned to ${params.departmentName} with ${params.priority} priority.`,
      complaintId: params.complaintId,
      read: false,
      createdAt: now
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.UPDATE, compCol);
  }
}

/**
 * Update complaint status (Admin or Department Staff)
 */
export async function updateComplaintStatus(params: {
  complaintDocId: string;
  complaintId: string;
  citizenUserId: string;
  previousStatus: ComplaintStatus;
  newStatus: ComplaintStatus;
  updatedBy: string;
  updatedByUid: string;
  role: 'admin' | 'staff' | 'citizen';
  note: string;
  rejectionReason?: string;
  resolutionProofUrl?: string;
  resolutionNotes?: string;
}): Promise<void> {
  const compCol = 'complaints';
  const now = new Date().toISOString();
  try {
    const ref = doc(db, compCol, params.complaintDocId);
    const updates: Record<string, any> = {
      status: params.newStatus,
      updatedAt: now
    };

    if (params.newStatus === 'Resolved') {
      updates.resolvedAt = now;
      if (params.resolutionProofUrl) updates.resolutionProofUrl = params.resolutionProofUrl;
      if (params.resolutionNotes) updates.resolutionNotes = params.resolutionNotes;
    }

    if (params.newStatus === 'Rejected' && params.rejectionReason) {
      updates.rejectionReason = params.rejectionReason;
    }

    await updateDoc(ref, updates);

    // Audit history trail
    await addDoc(collection(db, 'complaintUpdates'), {
      complaintId: params.complaintId,
      previousStatus: params.previousStatus,
      newStatus: params.newStatus,
      updatedBy: params.updatedBy,
      updatedByUid: params.updatedByUid,
      role: params.role,
      note: params.note || `Status transitioned to ${params.newStatus}.`,
      timestamp: now
    });

    // Notification for citizen
    await addDoc(collection(db, 'notifications'), {
      userId: params.citizenUserId,
      title: `Complaint Status: ${params.newStatus}`,
      message: `Complaint ${params.complaintId} is now ${params.newStatus}. Note: ${params.note}`,
      complaintId: params.complaintId,
      read: false,
      createdAt: now
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.UPDATE, compCol);
  }
}

/**
 * Reopen a complaint (Citizen action)
 */
export async function reopenComplaint(params: {
  complaintDocId: string;
  complaintId: string;
  citizenUserId: string;
  citizenName: string;
  reopenReason: string;
}): Promise<void> {
  const compCol = 'complaints';
  const now = new Date().toISOString();
  try {
    const ref = doc(db, compCol, params.complaintDocId);
    await updateDoc(ref, {
      status: 'Reopened',
      reopenReason: params.reopenReason,
      updatedAt: now
    });

    await addDoc(collection(db, 'complaintUpdates'), {
      complaintId: params.complaintId,
      previousStatus: 'Resolved',
      newStatus: 'Reopened',
      updatedBy: params.citizenName,
      updatedByUid: params.citizenUserId,
      role: 'citizen',
      note: `Reopened by citizen: ${params.reopenReason}`,
      timestamp: now
    });

    await addDoc(collection(db, 'notifications'), {
      userId: params.citizenUserId,
      title: 'Complaint Reopened',
      message: `Your complaint ${params.complaintId} has been reopened for further department review.`,
      complaintId: params.complaintId,
      read: false,
      createdAt: now
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.UPDATE, compCol);
  }
}

/**
 * Submit post-resolution citizen feedback
 */
export async function submitCitizenFeedback(params: {
  complaintId: string;
  userId: string;
  rating: number;
  comment: string;
}): Promise<void> {
  const feedbackCol = 'feedback';
  const now = new Date().toISOString();
  try {
    await addDoc(collection(db, feedbackCol), {
      complaintId: params.complaintId,
      userId: params.userId,
      rating: params.rating,
      comment: params.comment.trim(),
      createdAt: now
    });
  } catch (error) {
    handleFirestoreError(error, OperationType.CREATE, feedbackCol);
  }
}

/**
 * Fetch feedback for a complaint
 */
export async function fetchFeedbackForComplaint(complaintId: string): Promise<CitizenFeedback | null> {
  const feedbackCol = 'feedback';
  try {
    const q = query(collection(db, feedbackCol), where('complaintId', '==', complaintId), limit(1));
    const snap = await getDocs(q);
    if (!snap.empty) {
      return { ...snap.docs[0].data(), id: snap.docs[0].id } as CitizenFeedback;
    }
    return null;
  } catch (error) {
    handleFirestoreError(error, OperationType.GET, feedbackCol);
  }
}

/**
 * Fetch user notifications
 */
export async function fetchUserNotifications(userId: string): Promise<NotificationItem[]> {
  const notifCol = 'notifications';
  try {
    const q = query(
      collection(db, notifCol),
      where('userId', '==', userId),
      orderBy('createdAt', 'desc'),
      limit(50)
    );
    const snap = await getDocs(q);
    return snap.docs.map(d => ({ ...d.data(), id: d.id } as NotificationItem));
  } catch (error) {
    // Index fallback
    try {
      const qSimple = query(collection(db, notifCol), where('userId', '==', userId));
      const snap = await getDocs(qSimple);
      const items = snap.docs.map(d => ({ ...d.data(), id: d.id } as NotificationItem));
      return items.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    } catch (err2) {
      handleFirestoreError(error, OperationType.GET, notifCol);
    }
  }
}

/**
 * Mark notification as read
 */
export async function markNotificationAsRead(notifId: string): Promise<void> {
  const notifCol = 'notifications';
  try {
    const ref = doc(db, notifCol, notifId);
    await updateDoc(ref, { read: true });
  } catch (error) {
    handleFirestoreError(error, OperationType.UPDATE, notifCol);
  }
}
