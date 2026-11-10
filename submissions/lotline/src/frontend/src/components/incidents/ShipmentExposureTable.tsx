import React, { useState } from 'react';
import { Truck, Search, CheckCircle, Clock } from 'lucide-react';
import type { Shipment } from '../../services/api';

interface ShipmentExposureTableProps {
  shipments: Shipment[];
}

export const ShipmentExposureTable: React.FC<ShipmentExposureTableProps> = ({ shipments }) => {
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');

  const filtered = shipments.filter((s) => {
    const matchesSearch =
      s.shipment_id.toLowerCase().includes(search.toLowerCase()) ||
      s.retailer.toLowerCase().includes(search.toLowerCase()) ||
      s.lot_id.toLowerCase().includes(search.toLowerCase()) ||
      s.product_name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = filterStatus === 'ALL' || s.status === filterStatus;
    return matchesSearch && matchesStatus;
  });

  return (
    <section id="shipments" className="bento-opaque-card p-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5 border-b border-white/8">
        <div>
          <div className="flex items-center gap-2">
            <Truck className="w-4 h-4 text-[#23cad2]" />
            <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-white">
              SHIPMENT EXPOSURE TELEMETRY
            </h2>
          </div>
          <p className="text-xs text-white/50 mt-1">
            Real-time logistical tracking of batches dispatched to commercial retail partners
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-white/40 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search shipment, lot, retailer..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-black/40 border border-white/10 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-white/40 focus:outline-none focus:border-[#23cad2] transition-colors w-48 sm:w-60"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-black/40 border border-white/10 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-[#23cad2] transition-colors cursor-pointer"
          >
            <option value="ALL">All Status</option>
            <option value="DELIVERED">Delivered</option>
            <option value="IN_TRANSIT">In Transit</option>
          </select>
        </div>
      </div>

      {/* Table Container with Controlled Scroll */}
      <div className="overflow-x-auto mt-4">
        <table className="w-full text-left text-xs min-w-[640px]">
          <thead>
            <tr className="border-b border-white/8 text-[11px] font-mono text-white/50 uppercase whitespace-nowrap">
              <th className="py-3 px-3">Shipment ID</th>
              <th className="py-3 px-3">Product Lot</th>
              <th className="py-3 px-3">Product Name</th>
              <th className="py-3 px-3">Retailer Destination</th>
              <th className="py-3 px-3 text-right">Quantity</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3">Delivery Date</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 whitespace-nowrap">
            {filtered.map((s) => (
              <tr key={s.shipment_id} className="hover:bg-white/[0.02] transition-colors">
                <td className="py-3 px-3 font-mono font-bold text-[#8ef5e6]">
                  {s.shipment_id}
                </td>
                <td className="py-3 px-3 font-mono text-white/80">{s.lot_id}</td>
                <td className="py-3 px-3 text-white font-medium">{s.product_name}</td>
                <td className="py-3 px-3 text-white/90">{s.retailer}</td>
                <td className="py-3 px-3 font-mono font-bold text-white text-right">
                  {s.quantity.toLocaleString()} UNITS
                </td>
                <td className="py-3 px-3">
                  <span
                    className={`inline-flex items-center gap-1 text-[10px] font-mono font-bold px-2 py-0.5 rounded ${
                      s.status === 'DELIVERED'
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                    }`}
                  >
                    {s.status === 'DELIVERED' ? (
                      <CheckCircle className="w-2.5 h-2.5" />
                    ) : (
                      <Clock className="w-2.5 h-2.5" />
                    )}
                    {s.status}
                  </span>
                </td>
                <td className="py-3 px-3 font-mono text-white/50">
                  {s.delivery_date ? new Date(s.delivery_date).toLocaleString() : 'In Transit'}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-8 text-white/40 font-mono text-xs">
                  No shipments matching search criteria.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
};
