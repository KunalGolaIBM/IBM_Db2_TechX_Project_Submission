import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Polygon, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Compass, Edit3, Check, Trash2, Navigation, Search, Sparkles, ArrowRight, MapPin, X } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AiAssistantDrawer from '../components/common/AiAssistantDrawer';
import api from '../lib/api';

const DEFAULT_CENTER = [18.5204, 73.8567];
const ACRES_PER_HA = 2.47105381;
const formatArea = (value, digits = 2) => Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: digits });

function calculateAreaM2(coords = []) {
  if (coords.length < 3) return 0;
  const radius = 6378137;
  let sum = 0;
  for (let i = 0; i < coords.length; i += 1) {
    const next = coords[(i + 1) % coords.length];
    const lat1 = coords[i][0] * Math.PI / 180;
    const lat2 = next[0] * Math.PI / 180;
    const lng1 = coords[i][1] * Math.PI / 180;
    const lng2 = next[1] * Math.PI / 180;
    sum += (lng2 - lng1) * (2 + Math.sin(lat1) + Math.sin(lat2));
  }
  return Math.abs(sum * radius * radius / 2);
}

function calculatePerimeterM(coords = []) {
  return coords.reduce((sum, point, index) => {
    const next = coords[(index + 1) % coords.length];
    return sum + L.latLng(point).distanceTo(L.latLng(next));
  }, 0);
}

function MapController({ center, zoom }) {
  const map = useMap();
  useEffect(() => { if (center) map.setView(center, zoom, { animate: true }); }, [center, zoom, map]);
  return null;
}

function MapInteractions({ drawing, onAddPoint }) {
  useMapEvents({ click(event) { if (drawing) onAddPoint([event.latlng.lat, event.latlng.lng]); } });
  return null;
}

export default function LandAnalysis() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [parcels, setParcels] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [activeLayer, setActiveLayer] = useState('satellite');
  const [drawing, setDrawing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [points, setPoints] = useState([]);
  const [parcelName, setParcelName] = useState('');
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [searching, setSearching] = useState(false);
  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [gpsPoint, setGpsPoint] = useState(null);
  const [aiOpen, setAiOpen] = useState(false);

  const selected = parcels.find((parcel) => parcel.id === selectedId) || null;
  const activePoints = useMemo(() => drawing ? points : (selected?.coordinates || []), [drawing, points, selected]);
  const computedM2 = useMemo(() => calculateAreaM2(activePoints), [activePoints]);
  const computedPerimeter = useMemo(() => calculatePerimeterM(activePoints), [activePoints]);

  const loadParcels = React.useCallback(async (selectId) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.listParcels();
      const next = result.parcels || [];
      setParcels(next);
      if (selectId && next.some((parcel) => parcel.id === selectId)) setSelectedId(selectId);
      else if (!next.some((parcel) => parcel.id === selectedId)) setSelectedId(next[0]?.id || '');
      if (next.length) setCenter(next.find((parcel) => parcel.id === (selectId || selectedId))?.coordinates?.[0] || next[0].coordinates[0]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => { loadParcels(); }, [loadParcels]); // load saved parcel records from the backend

  const startDrawing = () => {
    setPoints(editing && selected ? selected.coordinates.map((point) => [...point]) : []);
    if (selected?.coordinates?.[0]) setCenter(selected.coordinates[0]);
    setDrawing(true);
    setEditing(Boolean(selected));
    setNotice('Click the map to add boundary vertices. GPS locates your device; it does not establish a property boundary.');
  };

  const saveBoundary = async () => {
    if (points.length < 3) {
      setError('Add at least three distinct vertices before saving a boundary.');
      return;
    }
    try {
      const payload = { name: parcelName.trim() || selected?.name || `Farm parcel ${parcels.length + 1}`, coordinates: points, location: selected?.location || `Map center ${points[0][0].toFixed(5)}, ${points[0][1].toFixed(5)}`, land_type: selected?.land_type || 'cropland' };
      const result = editing && selected
        ? await api.updateParcel(selected.id, { name: payload.name, coordinates: points })
        : await api.createParcel(payload);
      setCenter(result.parcel.coordinates[0]);
      setDrawing(false);
      setEditing(false);
      setPoints([]);
      setNotice('Boundary saved. It is a user-mapped outline, not a legally verified cadastral boundary.');
      await loadParcels(result.parcel.id);
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteParcel = async () => {
    if (!selected || !window.confirm(`Delete parcel “${selected.name}”?`)) return;
    try {
      await api.deleteParcel(selected.id);
      setNotice('Parcel deleted.');
      await loadParcels();
    } catch (err) { setError(err.message); }
  };

  const renameParcel = async () => {
    if (!selected) return;
    const name = window.prompt('Parcel name', selected.name);
    if (!name?.trim()) return;
    try {
      const result = await api.updateParcel(selected.id, { name: name.trim() });
      setParcels((previous) => previous.map((parcel) => parcel.id === selected.id ? result.parcel : parcel));
      setNotice('Parcel renamed.');
    } catch (err) { setError(err.message); }
  };

  const locateDevice = () => {
    if (!navigator.geolocation) { setError('This browser does not support device location.'); return; }
    setNotice('Requesting your location. Your browser will ask permission; location only centers the map.');
    navigator.geolocation.getCurrentPosition((position) => {
      const next = [position.coords.latitude, position.coords.longitude];
      setCenter(next);
      setGpsPoint(next);
      setNotice('Device location found. This identifies your device position only, not land ownership or a parcel boundary.');
    }, (err) => setError(`Location unavailable: ${err.message}`), { enableHighAccuracy: false, timeout: 10000 });
  };

  const searchLocation = async (event) => {
    event.preventDefault();
    if (!query.trim()) return;
    const coordinateMatch = query.trim().match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (coordinateMatch) {
      const next = [Number(coordinateMatch[1]), Number(coordinateMatch[2])];
      if (Math.abs(next[0]) <= 90 && Math.abs(next[1]) <= 180) { setCenter(next); setGpsPoint(null); return; }
      setError('Coordinates must be within latitude ±90 and longitude ±180.');
      return;
    }
    setSearching(true);
    setError('');
    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(query.trim())}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Location search failed (${response.status}).`);
      const results = await response.json();
      if (!results.length) throw new Error('No matching place found. Try a village, address, or latitude, longitude.');
      setCenter([Number(results[0].lat), Number(results[0].lon)]);
      setGpsPoint(null);
    } catch (err) { setError(err.message); }
    finally { setSearching(false); }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-5">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div><h2 className="text-xl font-bold text-[#0E2018]">Farm boundary mapping</h2><p className="text-sm text-[#638071]">Draw and save measured parcel outlines. Imagery is a visual reference, not an environmental measurement.</p></div>
        <form onSubmit={searchLocation} className="flex gap-2 w-full md:w-auto">
          <label className="sr-only" htmlFor="map-search">Search address, village, or coordinates</label>
          <input id="map-search" className="cn-input min-w-0 md:w-72" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Village, address, lat, lng" />
          <button className="btn-outline-forest" disabled={searching} aria-label="Search location"><Search size={16} />{searching ? 'Searching…' : 'Search'}</button>
        </form>
      </header>

      {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800 flex justify-between gap-3">{error}<button onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button></div>}
      {notice && <div role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">{notice}</div>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 items-start">
        <section className="lg:col-span-8 cn-card overflow-hidden h-[520px] md:h-[640px] relative" aria-label="Interactive parcel map">
          <div className="absolute z-[500] top-3 left-3 right-3 flex flex-wrap justify-between gap-2 pointer-events-none">
            <div className="bg-white/95 p-1 rounded-xl shadow flex gap-1 pointer-events-auto" aria-label="Map layer">
              {['satellite', 'terrain'].map((layer) => <button key={layer} onClick={() => setActiveLayer(layer)} className={`px-3 py-2 rounded-lg text-xs font-semibold capitalize ${activeLayer === layer ? 'bg-[#0C3327] text-white' : 'text-[#446654]'}`}>{layer}</button>)}
              <span className="px-2 py-2 text-[11px] text-[#526F60]">NDVI unavailable · no vegetation-index data source configured</span>
            </div>
            <div className="flex gap-2 pointer-events-auto">
              {!drawing ? <button onClick={startDrawing} className="bg-white px-3 py-2 rounded-xl text-xs font-semibold shadow flex gap-2 items-center"><Edit3 size={14} />{selected ? 'Redraw boundary' : 'Draw boundary'}</button> : <><button onClick={saveBoundary} disabled={points.length < 3} className="bg-[#0C3327] text-white px-3 py-2 rounded-xl text-xs font-semibold shadow disabled:opacity-50 flex gap-2 items-center"><Check size={14} />Save boundary</button><button onClick={() => { setDrawing(false); setPoints([]); setError(''); }} className="bg-white px-3 py-2 rounded-xl text-xs font-semibold shadow">Cancel</button></>}
              <button onClick={locateDevice} className="bg-white p-2 rounded-xl shadow" title="Locate my device (permission required)" aria-label="Locate my device"><Navigation size={17} /></button>
            </div>
          </div>
          {drawing && <div className="absolute z-[500] left-3 bottom-3 bg-white/95 p-2 rounded-lg text-xs shadow">{points.length} vertices · Click map to add{editing ? ' or drag markers to edit' : ''}<input aria-label="Parcel name" className="cn-input mt-2" value={parcelName} onChange={(event) => setParcelName(event.target.value)} placeholder={selected?.name || 'Parcel name'} /></div>}
          <MapContainer center={center} zoom={13} scrollWheelZoom zoomControl className="w-full h-full">
            <MapController center={center} zoom={13} />
            <MapInteractions drawing={drawing} onAddPoint={(point) => setPoints((previous) => [...previous, point])} />
            {activeLayer === 'satellite' ? <TileLayer attribution='Tiles &copy; Esri &mdash; Source: Esri, USGS, and the GIS User Community' url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" maxZoom={18} /> : <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19} />}
            {activePoints.length >= 3 && <Polygon positions={activePoints} pathOptions={{ color: '#fff', weight: 3, fillColor: '#10B981', fillOpacity: 0.35, dashArray: drawing ? '6 5' : undefined }} />}
            {drawing && points.map((point, index) => <Marker key={index} position={point} draggable={editing} eventHandlers={editing ? { dragend(event) { const next = event.target.getLatLng(); setPoints((previous) => previous.map((item, i) => i === index ? [next.lat, next.lng] : item)); } } : undefined} />)}
            {gpsPoint && <Marker position={gpsPoint}><Popup>Device location only; not a property boundary.</Popup></Marker>}
          </MapContainer>
          <div className="absolute bottom-3 right-3 z-[500] bg-white/90 rounded-lg px-3 py-2 text-[11px] text-[#365342]">Map imagery: Esri World Imagery · image acquisition date varies by tile</div>
        </section>

        <aside className="lg:col-span-4 space-y-4">
          <section className="cn-card p-5 space-y-3">
            <label htmlFor="parcel-select" className="block text-xs font-semibold uppercase text-[#5B7767]">Saved parcels</label>
            <select id="parcel-select" className="cn-input" value={selectedId} onChange={(event) => { setSelectedId(event.target.value); const parcel = parcels.find((item) => item.id === event.target.value); if (parcel) setCenter(parcel.coordinates[0]); }} disabled={!parcels.length}>
              {!parcels.length && <option value="">No saved boundaries yet</option>}
              {parcels.map((parcel) => <option key={parcel.id} value={parcel.id}>{parcel.name} · {formatArea(parcel.area_hectares)} ha</option>)}
            </select>
            {loading && <p className="text-sm text-[#638071]" role="status">Loading saved parcels…</p>}
            {!loading && !parcels.length && <p className="text-sm text-[#638071]">Draw a boundary to create your first parcel. No sample ownership or measurements are shown.</p>}
            {selected && <div className="flex gap-2"><button onClick={() => { setParcelName(selected.name); startDrawing(); }} className="btn-outline-forest text-xs flex-1"><Edit3 size={14} />Edit</button><button onClick={renameParcel} className="btn-outline-forest text-xs flex-1">Rename</button><button onClick={deleteParcel} className="btn-outline-forest text-xs text-red-700" aria-label="Delete parcel"><Trash2 size={14} /></button></div>}
          </section>

          {selected && <section className="cn-card p-5 space-y-4">
            <div className="flex items-center justify-between"><h3 className="font-bold text-[#0E2018]">{selected.name}</h3><span className="badge-sage">User-mapped</span></div>
            <dl className="space-y-3 text-sm"><div className="flex justify-between gap-3"><dt className="text-[#658172]">Area</dt><dd className="font-semibold text-right">{formatArea(computedM2, 0)} m²<br />{formatArea(computedM2 / 10000, 3)} ha · {formatArea(computedM2 / 4046.8564224, 3)} acres</dd></div><div className="flex justify-between"><dt className="text-[#658172]">Perimeter</dt><dd className="font-semibold">{formatArea(computedPerimeter / 1000, 3)} km</dd></div><div className="flex justify-between"><dt className="text-[#658172]">Vertices</dt><dd className="font-semibold">{selected.coordinates.length}</dd></div><div className="flex justify-between"><dt className="text-[#658172]">Mapped</dt><dd className="font-semibold">{new Date(selected.mapping_date).toLocaleDateString()}</dd></div></dl>
            <p className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">Area is calculated from the saved geospatial polygon. It is not a cadastral survey or legal verification.</p>
            <p className="text-[11px] text-[#638071]">Source: {selected.mapping_source}. Method: {selected.area_method}</p>
            <button onClick={() => { setParcelName(selected.name); setAiOpen(true); }} className="btn-outline-forest w-full text-xs"><Sparkles size={14} />Open evidence assistant</button>
            {selected.project_id && <button onClick={() => navigate(`/carbon-estimates?project=${encodeURIComponent(selected.project_id)}`)} className="btn-forest w-full text-xs">View associated assessment <ArrowRight size={14} /></button>}
          </section>}
          <p className="text-xs leading-relaxed text-[#638071]"><MapPin size={14} className="inline mr-1" />Location search uses OpenStreetMap Nominatim. Satellite/terrain tiles are third-party services. No NDVI or other satellite-derived environmental observations are currently connected.</p>
        </aside>
      </div>
      <AiAssistantDrawer isOpen={aiOpen} onClose={() => setAiOpen(false)} activeProject={selected?.project_id ? { id: selected.project_id, name: selected.name } : null} activeParcel={selected} />
    </div>
  );
}
