import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User as FirebaseUser,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut
} from 'firebase/auth';
import { doc, getDoc, setDoc, updateDoc } from 'firebase/firestore';
import { auth, db, googleProvider, handleFirestoreError, OperationType } from '../firebase';
import { UserProfile, UserRole } from '../types';

interface AuthContextType {
  currentUser: FirebaseUser | null;
  userProfile: UserProfile | null;
  loading: boolean;
  activeRole: UserRole;
  activeDepartment: string;
  setActiveRole: (role: UserRole) => void;
  setActiveDepartment: (dept: string) => void;
  loginWithGoogle: () => Promise<void>;
  loginAsDemoPersona: (role: UserRole, departmentName?: string) => Promise<void>;
  logout: () => Promise<void>;
  updateProfileData: (data: Partial<UserProfile>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const ADMIN_EMAILS = ['kaushikarya87@gmail.com'];

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentUser, setCurrentUser] = useState<FirebaseUser | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeRole, setActiveRole] = useState<UserRole>('citizen');
  const [activeDepartment, setActiveDepartment] = useState<string>('Public Works Department');

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (fbUser) => {
      if (fbUser) {
        setCurrentUser(fbUser);
        try {
          const userDocRef = doc(db, 'users', fbUser.uid);
          const snap = await getDoc(userDocRef);

          const isAdminEmail = fbUser.email && ADMIN_EMAILS.includes(fbUser.email.toLowerCase());
          let profile: UserProfile;

          if (snap.exists()) {
            profile = snap.data() as UserProfile;
            // Upgrade to admin if email matches
            if (isAdminEmail && profile.role !== 'admin') {
              profile.role = 'admin';
              await updateDoc(userDocRef, { role: 'admin' });
            }
          } else {
            profile = {
              uid: fbUser.uid,
              name: fbUser.displayName || 'Civic User',
              email: fbUser.email || '',
              role: isAdminEmail ? 'admin' : 'citizen',
              departmentName: isAdminEmail ? undefined : 'Public Works Department',
              createdAt: new Date().toISOString()
            };
            await setDoc(userDocRef, profile);
          }

          setUserProfile(profile);
          setActiveRole(profile.role);
          if (profile.departmentName) {
            setActiveDepartment(profile.departmentName);
          }
        } catch (err) {
          console.error('Error fetching or creating user profile:', err);
        }
      } else {
        // If not logged in with Google, check if demo persona exists in state
        if (!userProfile) {
          setCurrentUser(null);
          setUserProfile(null);
        }
      }
      setLoading(false);
    });

    return () => unsubscribe();
  }, []);

  const loginWithGoogle = async () => {
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (err) {
      console.error('Failed to sign in with Google:', err);
      throw err;
    }
  };

  /**
   * Demo persona login allows evaluating all 3 roles (Citizen, Admin, Staff)
   * while persisting in Firestore users collection
   */
  const loginAsDemoPersona = async (role: UserRole, departmentName = 'Public Works Department') => {
    const demoId = `demo-${role}-${role === 'staff' ? 'pwd' : 'user'}`;
    const demoNames: Record<UserRole, string> = {
      citizen: 'Rahul Sharma (Citizen)',
      admin: 'Kaushik Arya (Municipal Commissioner / Admin)',
      staff: 'Vikram Singh (PWD Field Supervisor)'
    };
    const demoEmails: Record<UserRole, string> = {
      citizen: 'citizen.rahul@civicconnect.local',
      admin: 'kaushikarya87@gmail.com',
      staff: 'vikram.pwd@civicconnect.local'
    };

    const profile: UserProfile = {
      uid: demoId,
      name: demoNames[role],
      email: demoEmails[role],
      role: role,
      departmentName: role === 'staff' ? departmentName : undefined,
      createdAt: new Date().toISOString()
    };

    try {
      await setDoc(doc(db, 'users', demoId), profile, { merge: true });
    } catch (err) {
      console.warn('Could not persist demo user to Firestore directly:', err);
    }

    setUserProfile(profile);
    setActiveRole(role);
    if (departmentName) {
      setActiveDepartment(departmentName);
    }
  };

  const logout = async () => {
    if (auth.currentUser) {
      await firebaseSignOut(auth);
    }
    setCurrentUser(null);
    setUserProfile(null);
    setActiveRole('citizen');
  };

  const updateProfileData = async (data: Partial<UserProfile>) => {
    if (!userProfile) return;
    const updated = { ...userProfile, ...data };
    setUserProfile(updated);
    try {
      await updateDoc(doc(db, 'users', userProfile.uid), data);
    } catch (err) {
      handleFirestoreError(err, OperationType.UPDATE, 'users');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        currentUser,
        userProfile,
        loading,
        activeRole,
        activeDepartment,
        setActiveRole,
        setActiveDepartment,
        loginWithGoogle,
        loginAsDemoPersona,
        logout,
        updateProfileData
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
