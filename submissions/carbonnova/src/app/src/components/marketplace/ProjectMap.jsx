import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { divIcon } from 'leaflet';
import { Leaf } from 'lucide-react';
import { renderToStaticMarkup } from 'react-dom/server';

const customMarkerIcon = divIcon({
  html: renderToStaticMarkup(
    <div className="w-8 h-8 rounded-full bg-carbon-500 border-2 border-white shadow-lg flex items-center justify-center text-white relative">
      <Leaf size={16} />
      <span className="absolute w-full h-full rounded-full animate-ping box-border border-2 border-carbon-500 bg-carbon-400 opacity-75"></span>
    </div>
  ),
  className: 'custom-marker',
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -16]
});

const ProjectMap = ({ project, devices }) => {
  if (!project) return null;

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-carbon-800/40 relative z-0">
       <MapContainer 
         center={[project.lat, project.lng]} 
         zoom={12} 
         scrollWheelZoom={false}
         className="w-full h-full"
       >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          className="leaflet-tile-dark"
        />
        <Marker position={[project.lat, project.lng]} icon={customMarkerIcon}>
          <Popup className="custom-popup">
            <div className="p-1">
               <h4 className="font-bold text-gray-800 text-sm mb-1">{project.name}</h4>
               <p className="text-xs text-gray-600 mb-2">{project.type} • {project.area_acres} acres</p>
               <div className="flex flex-col gap-1">
                 {devices?.map(d => (
                    <div key={d.id} className="flex items-center gap-1.5 text-xs text-gray-700">
                      <span className={`w-1.5 h-1.5 rounded-full ${d.is_active ? 'bg-emerald-500' : 'bg-red-500'}`} />
                      Sensor ID: {d.id}
                    </div>
                 ))}
               </div>
            </div>
          </Popup>
        </Marker>
      </MapContainer>
      
      {/* Custom Styles for Map Overrides to fit dark theme */}
      <style>{`
        .leaflet-container {
          background: #030d08 !important;
        }
        .leaflet-tile-dark {
          filter: brightness(0.6) invert(1) contrast(3) hue-rotate(200deg) saturate(0.3) brightness(0.7);
        }
        .custom-popup .leaflet-popup-content-wrapper {
          background: rgba(255, 255, 255, 0.95);
          backdrop-filter: blur(8px);
          border-radius: 12px;
          color: #1a1a1a;
          box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }
        .custom-popup .leaflet-popup-tip {
          background: rgba(255, 255, 255, 0.95);
        }
      `}</style>
    </div>
  );
};

export default ProjectMap;
