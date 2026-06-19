import React, { useState, useEffect } from 'react';
import { historyService } from '../services/historyService';
import { HistoryEvent, EventStatus, EventType } from '../types/history';
import HistoryDetailModal from '../components/history/HistoryDetailModal';

const DeploymentHistory: React.FC = () => {
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<HistoryEvent | null>(null);

  const [filters, setFilters] = useState<{ eventType?: EventType, timeRange?: string }>({});

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        setLoading(true);
        const { eventType, timeRange } = filters;
        let startDate: string | undefined;
        let endDate: string | undefined;

        if (timeRange) {
          const now = new Date();
          endDate = now.toISOString().split('T')[0];
          if (timeRange === 'today') {
            startDate = endDate;
          } else if (timeRange === 'week') {
            const weekAgo = new Date(now.setDate(now.getDate() - 7));
            startDate = weekAgo.toISOString().split('T')[0];
          } else if (timeRange === 'month') {
            const monthAgo = new Date(now.setMonth(now.getMonth() - 1));
            startDate = monthAgo.toISOString().split('T')[0];
          }
        }

        const response = await historyService.getHistory(page, 10, eventType, startDate, endDate);
        setHistory(response.events);
        setTotalPages(response.total_pages || 1);
        setTotal(response.total);
      } catch (err) {
        setError('Gagal memuat riwayat deployment.');
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [page, filters]);

  const handleFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
    setPage(1); // Reset to first page on filter change
  };

  const getStatusChip = (status: EventStatus) => {
    const baseClasses = "px-2 inline-flex text-xs leading-5 font-semibold rounded-full";
    switch (status) {
      case EventStatus.SUCCESS:
        return `${baseClasses} bg-green-100 text-green-800`;
      case EventStatus.FAILED:
        return `${baseClasses} bg-red-100 text-red-800`;
      case EventStatus.IN_PROGRESS:
        return `${baseClasses} bg-yellow-100 text-yellow-800`;
      case EventStatus.PENDING:
        return `${baseClasses} bg-gray-100 text-gray-800`;
      default:
        return baseClasses;
    }
  };

  const formatEventType = (eventType: EventType) => {
    return eventType.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Riwayat Deployment</h1>
      
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Aktivitas Terbaru</h2>
        <p className="text-gray-600">
          Lihat riwayat aktivitas dan deployment virtual machine Anda.
          Riwayat ini menampilkan semua operasi create, start, stop, dan delete VM.
        </p>
      </div>
      
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="p-4 border-b">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium">Filter</h3>
            <div className="flex space-x-2">
              <select name="eventType" onChange={handleFilterChange} className="border rounded px-3 py-1 text-sm">
                <option value="">Semua Aktivitas</option>
                <option value={EventType.VM_CREATE}>Buat VM</option>
                <option value={EventType.VM_START}>Start VM</option>
                <option value={EventType.VM_STOP}>Stop VM</option>
                <option value={EventType.VM_DELETE}>Delete VM</option>
              </select>
              <select name="timeRange" onChange={handleFilterChange} className="border rounded px-3 py-1 text-sm">
                <option value="">Semua Waktu</option>
                <option value="today">Hari Ini</option>
                <option value="week">Minggu Ini</option>
                <option value="month">Bulan Ini</option>
              </select>
            </div>
          </div>
        </div>
        
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Tanggal
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Aktivitas
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                VM
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Detail
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-center text-gray-500" colSpan={5}>
                  Memuat...
                </td>
              </tr>
            ) : error ? (
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-center text-red-500" colSpan={5}>
                  {error}
                </td>
              </tr>
            ) : history.length === 0 ? (
              <tr>
                <td className="px-6 py-4 whitespace-nowrap text-center text-gray-500" colSpan={5}>
                  Belum ada riwayat deployment.
                </td>
              </tr>
            ) : (
              history.map((event) => (
                <tr key={event.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(event.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {formatEventType(event.event_type)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {event.vm_name || `VM ID: ${event.vm_id}` || 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={getStatusChip(event.status)}>
                      {event.status}
                    </span>
                  </td>
                  <td onClick={() => setSelectedEvent(event)} className="px-6 py-4 whitespace-nowrap text-sm text-blue-500 hover:underline cursor-pointer">
                    Lihat Detail
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        
        <div className="bg-gray-50 px-4 py-3 border-t border-gray-200 sm:px-6">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-700">
              Showing <span className="font-medium">{(page - 1) * 10 + 1}</span> to <span className="font-medium">{Math.min(page * 10, total)}</span> of <span className="font-medium">{total}</span> results
            </div>
            <div>
              <button 
                onClick={() => setPage(page - 1)}
                disabled={page === 1} 
                className="px-3 py-1 border rounded bg-white text-gray-700 hover:bg-gray-50 disabled:bg-gray-200 disabled:text-gray-400 mr-2"
              >
                Previous
              </button>
              <button 
                onClick={() => setPage(page + 1)}
                disabled={page >= totalPages} 
                className="px-3 py-1 border rounded bg-white text-gray-700 hover:bg-gray-50 disabled:bg-gray-200 disabled:text-gray-400"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
      <HistoryDetailModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
};

export default DeploymentHistory;
