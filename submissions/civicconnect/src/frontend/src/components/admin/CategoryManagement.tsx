import React from 'react';
import {
  Tag,
  Building,
  Trash2,
  Construction,
  Lightbulb,
  Droplets,
  Waves,
  ShieldAlert,
  HelpCircle,
  FolderClock
} from 'lucide-react';
import { CIVIC_CATEGORIES, Complaint } from '../../types';

interface CategoryManagementProps {
  complaints: Complaint[];
}

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  'Garbage Collection': Trash2,
  'Road Damage / Potholes': Construction,
  'Streetlight Problems': Lightbulb,
  'Water Leakage': Droplets,
  'Drainage and Sewage': Waves,
  'Public Property Damage': ShieldAlert,
  'Other Civic Issues': HelpCircle,
};

export const CategoryManagement: React.FC<CategoryManagementProps> = ({ complaints }) => {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Complaint Categories & Routing Rules</h1>
        <p className="text-xs text-slate-500">
          Standardized civic taxonomy mapped to recommended municipal departments
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {CIVIC_CATEGORIES.map((cat, idx) => {
          const Icon = CATEGORY_ICONS[cat.name] || Tag;
          const count = complaints.filter(c => c.category === cat.name).length;
          const resolved = complaints.filter(c => c.category === cat.name && c.status === 'Resolved').length;

          return (
            <div
              key={cat.name}
              className="p-5 rounded-2xl bg-white border border-slate-200/90 shadow-xs flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center border border-teal-200">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] font-mono font-bold bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                    CAT-0{idx + 1}
                  </span>
                </div>

                <h3 className="text-base font-bold text-slate-900">{cat.name}</h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">{cat.description}</p>

                <div className="mt-4 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center gap-2">
                  <Building className="w-4 h-4 text-teal-600 shrink-0" />
                  <div className="overflow-hidden">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block">Default Department</span>
                    <span className="text-xs font-semibold text-slate-800 truncate block">
                      {cat.defaultDepartment}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                <span>Total Reported: <strong className="text-slate-900">{count}</strong></span>
                <span>Resolved: <strong className="text-emerald-700">{resolved}</strong></span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
