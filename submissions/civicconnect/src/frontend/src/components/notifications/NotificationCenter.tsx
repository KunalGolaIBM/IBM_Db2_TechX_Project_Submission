import React, { useState, useEffect } from 'react';
import {
  Bell,
  CheckCircle2,
  Clock,
  ArrowRight,
  Check,
  Building,
  RotateCcw,
  ShieldCheck,
  Loader2
} from 'lucide-react';
import { NotificationItem, Complaint } from '../../types';
import { useAuth } from '../../context/AuthContext';
import { fetchUserNotifications, markNotificationAsRead } from '../../services/complaintService';

interface NotificationCenterProps {
  onSelectComplaintId: (complaintId: string) => void;
}

export const NotificationCenter: React.FC<NotificationCenterProps> = ({ onSelectComplaintId }) => {
  const { userProfile, currentUser } = useAuth();
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const uid = userProfile?.uid || currentUser?.uid;
    if (!uid) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const items = await fetchUserNotifications(uid);
      setNotifications(items || []);
    } catch (err) {
      console.warn('Error loading notifications:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [userProfile?.uid, currentUser?.uid]);

  const handleMarkAllRead = async () => {
    for (const n of notifications) {
      if (!n.read) {
        await markNotificationAsRead(n.id);
      }
    }
    await load();
  };

  const handleClickItem = async (n: NotificationItem) => {
    if (!n.read) {
      await markNotificationAsRead(n.id);
    }
    if (n.complaintId) {
      onSelectComplaintId(n.complaintId);
    }
  };

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="max-w-3xl mx-auto space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-slate-900">In-App Notification Center</h1>
            {unreadCount > 0 && (
              <span className="text-xs bg-teal-100 text-teal-800 font-bold px-2 py-0.5 rounded-full">
                {unreadCount} unread
              </span>
            )}
          </div>
          <p className="text-xs text-slate-500">Live system updates, department assignments, and resolution alerts</p>
        </div>

        {unreadCount > 0 && (
          <button
            type="button"
            onClick={handleMarkAllRead}
            className="self-start sm:self-center px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition flex items-center gap-1.5"
          >
            <Check className="w-3.5 h-3.5 text-teal-600" />
            <span>Mark All as Read</span>
          </button>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/90 shadow-xs divide-y divide-slate-100 overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-xs text-slate-400">
            <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2 text-teal-600" />
            Loading notifications...
          </div>
        ) : notifications.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">
            <Bell className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="font-semibold text-slate-700">No notifications in your queue</p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              You will receive real-time updates when complaints are registered, assigned to departments, or resolved.
            </p>
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              onClick={() => handleClickItem(n)}
              className={`p-4 hover:bg-slate-50 cursor-pointer transition flex items-start justify-between gap-3 ${
                !n.read ? 'bg-teal-50/40 border-l-4 border-l-teal-600' : ''
              }`}
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-900">{n.title}</span>
                  {!n.read && (
                    <span className="w-2 h-2 rounded-full bg-teal-500 inline-block" />
                  )}
                  {n.complaintId && (
                    <span className="font-mono text-[10px] font-bold text-teal-800 bg-teal-100 px-1.5 py-0.2 rounded">
                      {n.complaintId}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">{n.message}</p>
                <span className="text-[10px] text-slate-400 block">
                  {new Date(n.createdAt).toLocaleDateString([], {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </span>
              </div>

              {n.complaintId && (
                <button
                  type="button"
                  className="shrink-0 p-1.5 text-slate-400 hover:text-teal-700 hover:bg-slate-100 rounded-lg transition"
                  title="View Complaint"
                >
                  <ArrowRight className="w-4 h-4" />
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
