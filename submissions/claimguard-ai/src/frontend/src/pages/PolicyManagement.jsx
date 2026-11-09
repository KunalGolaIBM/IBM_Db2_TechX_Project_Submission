import React, { useEffect, useState } from 'react';
import { BookOpen, User, Shield, RefreshCw, CheckCircle, Search, DollarSign } from 'lucide-react';
import { apiClient } from '../api/client';

export default function PolicyManagement() {
  const [policies, setPolicies] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [activeTab, setActiveTab] = useState('POLICIES');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [polRes, custRes] = await Promise.all([
        apiClient.getPolicies(),
        apiClient.getCustomers(),
      ]);
      setPolicies(polRes.data);
      setCustomers(custRes.data);
    } catch (err) {
      console.error('Failed to load policies/customers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const filteredPolicies = policies.filter((p) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      p.policy_number.toLowerCase().includes(q) ||
      p.policy_id.toLowerCase().includes(q) ||
      p.customer_id.toLowerCase().includes(q) ||
      p.policy_type.toLowerCase().includes(q)
    );
  });

  const filteredCustomers = customers.filter((c) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      c.customer_id.toLowerCase().includes(q) ||
      c.first_name.toLowerCase().includes(q) ||
      c.last_name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-[#E0E0E0]">
        <div>
          <div className="flex items-center space-x-2">
            <div className="p-1.5 bg-[#EDF5FF] text-[#0F62FE] rounded">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[#161616]">Policy & Customer Management</h1>
              <p className="text-xs text-[#525252]">
                Synchronized records from IBM Db2 POLICY_DETAILS and CUSTOMER_DETAILS
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={fetchData}
          className="flex items-center space-x-1 px-3 py-1.5 text-xs bg-white border border-[#E0E0E0] hover:bg-gray-50 text-[#161616] rounded-sm transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Tabs and Search */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-white border border-[#E0E0E0] p-3 rounded-sm shadow-sm">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setActiveTab('POLICIES')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-sm uppercase font-mono transition-colors ${
              activeTab === 'POLICIES'
                ? 'bg-[#0F62FE] text-white'
                : 'bg-gray-100 text-[#525252] hover:bg-gray-200'
            }`}
          >
            Policies ({policies.length})
          </button>
          <button
            onClick={() => setActiveTab('CUSTOMERS')}
            className={`px-3 py-1.5 text-xs font-semibold rounded-sm uppercase font-mono transition-colors ${
              activeTab === 'CUSTOMERS'
                ? 'bg-[#0F62FE] text-white'
                : 'bg-gray-100 text-[#525252] hover:bg-gray-200'
            }`}
          >
            Customers ({customers.length})
          </button>
        </div>

        <div className="relative w-full md:w-72">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search policies or customers..."
            className="w-full pl-9 pr-3 py-1.5 bg-[#F4F4F4] border border-[#E0E0E0] text-xs text-[#161616] rounded-sm focus:outline-none focus:border-[#0F62FE] focus:bg-white"
          />
        </div>
      </div>

      {activeTab === 'POLICIES' ? (
        <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
                <tr>
                  <th className="py-3 px-3">Policy # / ID</th>
                  <th className="py-3 px-3">Customer ID</th>
                  <th className="py-3 px-3">Type</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Max Coverage</th>
                  <th className="py-3 px-3">Remaining Balance</th>
                  <th className="py-3 px-3">Deductible</th>
                  <th className="py-3 px-3">Validity Window</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 font-mono">
                {filteredPolicies.map((p) => (
                  <tr key={p.policy_id} className="hover:bg-gray-50">
                    <td className="py-3 px-3 font-semibold text-[#0F62FE]">
                      {p.policy_number}
                      <span className="block text-[10px] text-gray-400">{p.policy_id}</span>
                    </td>
                    <td className="py-3 px-3 text-gray-700">{p.customer_id}</td>
                    <td className="py-3 px-3 font-sans text-gray-900 font-medium">{p.policy_type}</td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                        {p.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 font-semibold text-gray-900">
                      ₹{parseFloat(p.max_coverage_amount).toLocaleString()}
                    </td>
                    <td className="py-3 px-3 font-bold text-[#0F62FE]">
                      ₹{parseFloat(p.remaining_coverage).toLocaleString()}
                    </td>
                    <td className="py-3 px-3 text-gray-600">
                      ₹{parseFloat(p.deductible || 0).toLocaleString()}
                    </td>
                    <td className="py-3 px-3 text-gray-500 text-[11px]">
                      {p.start_date} to {p.end_date}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-[#E0E0E0] rounded-sm shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#F4F4F4] text-[#525252] border-b border-[#E0E0E0] uppercase font-mono text-[10px]">
                <tr>
                  <th className="py-3 px-3">Customer ID</th>
                  <th className="py-3 px-3">Full Name</th>
                  <th className="py-3 px-3">Email Address</th>
                  <th className="py-3 px-3">Phone</th>
                  <th className="py-3 px-3">National ID</th>
                  <th className="py-3 px-3">Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredCustomers.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-gray-50">
                    <td className="py-3 px-3 font-mono font-semibold text-[#0F62FE]">{c.customer_id}</td>
                    <td className="py-3 px-3 font-medium text-gray-900">{c.first_name} {c.last_name}</td>
                    <td className="py-3 px-3 text-gray-600">{c.email}</td>
                    <td className="py-3 px-3 font-mono text-gray-600">{c.phone || 'N/A'}</td>
                    <td className="py-3 px-3 font-mono text-gray-700">{c.national_id || 'N/A'}</td>
                    <td className="py-3 px-3 text-gray-600 max-w-xs truncate">{c.address || 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
