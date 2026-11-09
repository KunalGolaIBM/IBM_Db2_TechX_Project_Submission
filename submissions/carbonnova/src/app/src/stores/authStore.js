import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { mockUsers } from '../lib/mockData';

const DEFAULT_USER = {
  id: 'user-alex',
  email: 'alex.carter@carbonnova.earth',
  full_name: 'Alex Carter',
  organization: 'Green Valley Agroforestry & Land Trust',
  role: 'seller',
  avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256',
};

const DEMO_ROLE_USERS = {
  seller: { id: 'user-seller-1', email: 'asha@seller.demo', full_name: 'Asha Patel', organization: 'Green Valley Cooperative', role: 'seller', demo: true, avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256' },
  buyer: { id: 'user-buyer-1', email: 'jordan@buyer.demo', full_name: 'Jordan Lee', organization: 'Northwind Climate Fund', role: 'buyer', demo: true },
  admin: { id: 'user-admin-1', email: 'admin@carbonnova.demo', full_name: 'Platform Admin', organization: 'CarbonNova', role: 'admin', demo: true },
};

export const useAuthStore = create(
  persist(
    (set) => ({
      user: DEFAULT_USER,
      isAuthenticated: true,
      demoRole: null,
      selectDemoRole: (role) => {
        const userData = DEMO_ROLE_USERS[role] || DEMO_ROLE_USERS.seller;
        set({ user: userData, isAuthenticated: true, demoRole: role });
      },
      clearDemoRole: () => set({ demoRole: null, user: DEFAULT_USER }),
      login: (email, role = 'seller') => {
        const existingUser = mockUsers.find((u) => u.email === email);
        const userData = existingUser || {
          id: `user-${Date.now()}`,
          email,
          role,
          full_name: email.split('@')[0],
        };
        set({ user: userData, isAuthenticated: true });
      },
      logout: () => {
        set({ user: null, isAuthenticated: false, demoRole: null });
      },
      setUser: (user) => set({ user, isAuthenticated: Boolean(user) }),
    }),
    {
      name: 'carbonnova-auth',
    }
  )
);
