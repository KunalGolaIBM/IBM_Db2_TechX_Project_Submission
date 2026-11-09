import React, { useState } from 'react';
import {
  Plus,
  MapPin,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { useProjects } from '../hooks/useApi';
import api from '../lib/api';
import AiAssistantDrawer from '../components/common/AiAssistantDrawer';

const LIFECYCLE_STAGES = ['Draft', 'Data collection', 'Assessment', 'Validation pending', 'Verification pending', 'Independently verified', 'Registered / issued', 'Retired'];

export const ProjectsPage = () => {
  const projectsQ = useProjects();
  const [modalOpen, setModalOpen] = useState(false);
  const [isAiOpen, setIsAiOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);

  // New Project Form State
  const [formData, setFormData] = useState({
    name: '',
    land_type: 'agroforestry',
    area_acres: 100,
    location: '',
    description: '',
    methodology: 'Verra VM0042',
  });

  const projects = projectsQ.data?.projects || [];

  const handleCreateProject = async (e) => {
    e.preventDefault();
    try {
      await api.createProject({
        ...formData,
        area_acres: Number(formData.area_acres),
        owner_id: 'user-1',
      });
      projectsQ.refetch();
      setModalOpen(false);
      setFormData({
        name: '',
        land_type: 'agroforestry',
        area_acres: 100,
        location: '',
        description: '',
        methodology: 'Verra VM0042',
      });
    } catch (err) {
      alert(`Could not create project: ${err.message}`);
    }
  };


  return (
    <div className="max-w-7xl mx-auto space-y-6">
      
      {/* Top Action Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-[#0E2018]">Carbon Project Portfolio</h2>
          <p className="text-xs text-[#638071]">Organize project records and evidence gaps. Verification and registry status require supporting records.</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsAiOpen(true)}
            className="btn-outline-forest text-xs py-2 px-3.5 flex items-center gap-1.5"
          >
            <Sparkles size={14} className="text-[#10B981]" />
            <span>AI Project Assistant</span>
          </button>

          <button
            onClick={() => setModalOpen(true)}
            className="btn-forest text-xs py-2 px-4 flex items-center gap-2"
          >
            <Plus size={15} />
            <span>New Carbon Project</span>
          </button>
        </div>
      </div>

      <div className="cn-card p-6 bg-white shadow-xs"><h4 className="text-xs font-bold text-[#557363] uppercase tracking-wider mb-3">Lifecycle vocabulary</h4><div className="flex flex-wrap gap-2">{LIFECYCLE_STAGES.map((stage) => <span key={stage} className="badge-sage">{stage}</span>)}</div><p className="mt-3 text-xs text-[#638071]">Labels are not milestones: no validation, verification, registration, issuance, or retirement is asserted without a record.</p></div>

      {/* Projects Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {projectsQ.isLoading && <p role="status" className="cn-card p-5">Loading saved projects…</p>}
        {projectsQ.isError && <p role="alert" className="cn-card p-5 text-red-800">Could not load projects: {projectsQ.error.message}</p>}
        {!projectsQ.isLoading && !projectsQ.isError && !projects.length && <p className="cn-card p-5 text-[#638071]">No saved projects. Map a parcel to start a project record.</p>}
        {projects.map((proj) => {
          const areaHa = (proj.area_hectares || proj.area_acres * 0.404686).toFixed(1);
          return (
            <div
              key={proj.id}
              className="cn-card-hover p-6 flex flex-col justify-between bg-white"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-3">
                  <div>
                    <h3 className="font-bold text-base text-[#0E2018]">{proj.name}</h3>
                    <p className="text-xs text-[#638071] flex items-center gap-1 mt-0.5">
                      <MapPin size={12} /> {proj.location || 'Location specified'}
                    </p>
                  </div>
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-[#E8F7F0] text-[#0A7B4E] border border-[#BCE8D5]">
                    {proj.status || 'Active'}
                  </span>
                </div>

                <p className="text-xs text-[#526F60] line-clamp-2 leading-relaxed mb-4">
                  {proj.description || 'Land-based carbon management initiative following international accounting standards.'}
                </p>

                <div className="grid grid-cols-2 gap-2 text-xs py-3 border-y border-[#EDF2EE] my-3">
                  <div>
                    <span className="text-[10px] text-gray-400 block uppercase">Area</span>
                    <span className="font-bold text-[#0E2018]">{areaHa} ha</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-400 block uppercase">Land Type</span>
                    <span className="font-semibold text-[#183628] capitalize">{proj.land_type}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-400 block uppercase">Methodology</span>
                    <span className="font-semibold text-emerald-800">Not selected</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-gray-400 block uppercase">dMRV Status</span>
                    <span className="font-semibold text-[#0E2018]">{proj.reading_count ? `${proj.reading_count} stored readings` : 'No readings'}</span>
                  </div>
                </div>
              </div>

              <div className="pt-3 flex items-center justify-between">
                <button
                  onClick={() => {
                    setSelectedProject(proj);
                    setIsAiOpen(true);
                  }}
                  className="text-xs font-semibold text-[#0A7B4E] hover:underline flex items-center gap-1"
                >
                  <Sparkles size={13} /> AI Summary
                </button>

                <span className="text-xs font-bold text-[#0C3327] flex items-center gap-1">
                  View Detail <ChevronRight size={14} />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* CREATE PROJECT MODAL */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-[#D5E0D7] animate-in zoom-in-95 duration-150">
            <h3 className="font-bold text-lg text-[#0E2018] mb-1">Create New Carbon Project</h3>
            <p className="text-xs text-[#627F70] mb-5">Create a draft data-collection record. No carbon methodology or verification status is implied.</p>

            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-[#183628] mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Western Ghats Agroforestry Corridor"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="cn-input text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#183628] mb-1">Land Type</label>
                  <select
                    value={formData.land_type}
                    onChange={(e) => setFormData({ ...formData, land_type: e.target.value })}
                    className="cn-input text-xs"
                  >
                    <option value="agroforestry">Agroforestry</option>
                    <option value="cropland">Cropland (Regenerative)</option>
                    <option value="forestry">Reforestation / Forestry</option>
                    <option value="pasture">Grassland / Pasture</option>
                    <option value="mangrove">Coastal Mangrove</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#183628] mb-1">Area (Acres)</label>
                  <input
                    type="number"
                    required
                    value={formData.area_acres}
                    onChange={(e) => setFormData({ ...formData, area_acres: e.target.value })}
                    className="cn-input text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#183628] mb-1">Location / Coordinates</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Pune, Maharashtra, India"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  className="cn-input text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#183628] mb-1">Methodology Standard</label>
                <select
                  value={formData.methodology}
                  onChange={(e) => setFormData({ ...formData, methodology: e.target.value })}
                  className="cn-input text-xs"
                >
                  <option value="Verra VM0042">Verra VM0042 (Improved Agricultural Land Management)</option>
                  <option value="Gold Standard SOC">Gold Standard Soil Organic Carbon</option>
                  <option value="IPCC Tier 2 AFOLU">IPCC Tier 2 AFOLU Protocol</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#183628] mb-1">Description</label>
                <textarea
                  rows="3"
                  placeholder="Describe practices, tree species, soil interventions..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="cn-input text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#EDF2EE]">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="btn-outline-forest text-xs py-2 px-4"
                >
                  Cancel
                </button>
                <button type="submit" className="btn-forest text-xs py-2 px-5">
                  Save Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AI Assistant Context Drawer */}
      <AiAssistantDrawer
        isOpen={isAiOpen}
        onClose={() => setIsAiOpen(false)}
        activeProject={selectedProject}
      />
    </div>
  );
};

export default ProjectsPage;
