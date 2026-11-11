import React, { useState, useEffect } from 'react';
import {
  Building,
  Plus,
  Edit2,
  CheckCircle2,
  XCircle,
  FolderClock,
  Check,
  X,
  Loader2,
  ShieldCheck
} from 'lucide-react';
import { Department, Complaint } from '../../types';
import { fetchDepartments, saveDepartment } from '../../services/complaintService';

interface DepartmentManagementProps {
  complaints: Complaint[];
}

export const DepartmentManagement: React.FC<DepartmentManagementProps> = ({ complaints }) => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [currentEdit, setCurrentEdit] = useState<Partial<Department>>({});
  const [saving, setSaving] = useState<boolean>(false);

  const loadDepts = async () => {
    setLoading(true);
    try {
      const list = await fetchDepartments();
      setDepartments(list || []);
    } catch (err) {
      console.warn('Error loading departments:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDepts();
  }, []);

  const handleOpenAdd = () => {
    setCurrentEdit({
      name: '',
      description: '',
      active: true,
      suggestedCategories: []
    });
    setIsEditing(true);
  };

  const handleOpenEdit = (dept: Department) => {
    setCurrentEdit(dept);
    setIsEditing(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentEdit.name?.trim()) return;
    setSaving(true);
    try {
      await saveDepartment({
        ...currentEdit,
        name: currentEdit.name.trim()
      });
      setIsEditing(false);
      await loadDepts();
    } catch (err: any) {
      alert('Error saving department: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleActive = async (dept: Department) => {
    try {
      await saveDepartment({
        ...dept,
        active: !dept.active
      });
      await loadDepts();
    } catch (err: any) {
      alert('Error updating status: ' + err.message);
    }
  };

  // Compute live department stats from complaints collection
  const getDeptStats = (deptName: string) => {
    const assigned = complaints.filter(c => c.departmentName === deptName);
    const total = assigned.length;
    const pending = assigned.filter(c => c.status !== 'Resolved' && c.status !== 'Rejected').length;
    const resolved = assigned.filter(c => c.status === 'Resolved').length;
    return { total, pending, resolved };
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Municipal Departments</h1>
          <p className="text-xs text-slate-500">Configure civic departments, assigned categories, and monitor service workloads</p>
        </div>
        <button
          type="button"
          onClick={handleOpenAdd}
          className="self-start sm:self-center px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-500 text-white text-xs font-semibold shadow-xs transition flex items-center gap-1.5"
        >
          <Plus className="w-4 h-4" />
          <span>Add Department</span>
        </button>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-slate-400 bg-white rounded-xl border border-slate-200">
          <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-teal-600" />
          Loading municipal departments...
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {departments.map((dept) => {
            const stats = getDeptStats(dept.name);
            return (
              <div
                key={dept.id || dept.departmentId}
                className={`p-5 rounded-2xl bg-white border transition shadow-xs flex flex-col justify-between ${
                  dept.active ? 'border-slate-200/90' : 'border-slate-200 opacity-60 bg-slate-50'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[11px] font-bold text-slate-500 uppercase bg-slate-100 px-2 py-0.5 rounded">
                      {dept.departmentId}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleToggleActive(dept)}
                      className={`text-xs px-2 py-0.5 rounded-full font-semibold border flex items-center gap-1 transition ${
                        dept.active
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                          : 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
                      }`}
                      title="Click to toggle department status"
                    >
                      {dept.active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      <span>{dept.active ? 'Active' : 'Deactivated'}</span>
                    </button>
                  </div>

                  <h3 className="text-base font-bold text-slate-900">{dept.name}</h3>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">{dept.description}</p>

                  {dept.suggestedCategories && dept.suggestedCategories.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {dept.suggestedCategories.map((sc, i) => (
                        <span key={i} className="text-[10px] bg-teal-50 text-teal-800 border border-teal-100 px-1.5 py-0.5 rounded">
                          {sc}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100">
                  <div className="grid grid-cols-3 gap-2 text-center text-xs mb-3">
                    <div className="bg-slate-50 p-1.5 rounded-lg">
                      <span className="text-[10px] text-slate-400 block">Total</span>
                      <strong className="text-slate-800 text-sm font-bold">{stats.total}</strong>
                    </div>
                    <div className="bg-amber-50 p-1.5 rounded-lg">
                      <span className="text-[10px] text-amber-700 block">Pending</span>
                      <strong className="text-amber-800 text-sm font-bold">{stats.pending}</strong>
                    </div>
                    <div className="bg-emerald-50 p-1.5 rounded-lg">
                      <span className="text-[10px] text-emerald-700 block">Resolved</span>
                      <strong className="text-emerald-800 text-sm font-bold">{stats.resolved}</strong>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleOpenEdit(dept)}
                    className="w-full py-1.5 px-3 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold transition flex items-center justify-center gap-1.5"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                    <span>Edit Configuration</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit / Add Modal */}
      {isEditing && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-slate-200 w-full max-w-md p-6 animate-fadeIn">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 mb-4">
              <h3 className="text-base font-bold text-slate-900">
                {currentEdit.id ? 'Edit Department' : 'Add New Municipal Department'}
              </h3>
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSave} className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase text-slate-700 mb-1">
                  Department Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={currentEdit.name || ''}
                  onChange={(e) => setCurrentEdit({ ...currentEdit, name: e.target.value })}
                  placeholder="e.g. Parks & Recreation Department"
                  required
                  className="w-full px-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase text-slate-700 mb-1">
                  Description
                </label>
                <textarea
                  rows={3}
                  value={currentEdit.description || ''}
                  onChange={(e) => setCurrentEdit({ ...currentEdit, description: e.target.value })}
                  placeholder="Role, scope of responsibility, and infrastructure covered..."
                  className="w-full px-3 py-2 text-xs sm:text-sm rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-teal-500"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="activeToggle"
                  checked={currentEdit.active ?? true}
                  onChange={(e) => setCurrentEdit({ ...currentEdit, active: e.target.checked })}
                  className="rounded text-teal-600 focus:ring-teal-500 w-4 h-4"
                />
                <label htmlFor="activeToggle" className="text-xs font-medium text-slate-700">
                  Active department (accepts incoming complaint routing)
                </label>
              </div>

              <div className="pt-3 border-t border-slate-200 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-4 py-2 text-xs rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-teal-600 hover:bg-teal-500 text-white shadow-xs"
                >
                  {saving ? 'Saving...' : 'Save Department'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
