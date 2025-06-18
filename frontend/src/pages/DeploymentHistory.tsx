import React from 'react';

const DeploymentHistory: React.FC = () => {
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
              <select className="border rounded px-3 py-1 text-sm">
                <option>Semua Aktivitas</option>
                <option>Buat VM</option>
                <option>Start VM</option>
                <option>Stop VM</option>
                <option>Delete VM</option>
              </select>
              <select className="border rounded px-3 py-1 text-sm">
                <option>Semua Waktu</option>
                <option>Hari Ini</option>
                <option>Minggu Ini</option>
                <option>Bulan Ini</option>
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
            <tr>
              <td className="px-6 py-4 whitespace-nowrap text-gray-500" colSpan={5}>
                Belum ada riwayat deployment.
              </td>
            </tr>
          </tbody>
        </table>
        
        <div className="bg-gray-50 px-4 py-3 border-t border-gray-200 sm:px-6">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-700">
              Showing <span className="font-medium">0</span> results
            </div>
            <div>
              <button disabled className="px-3 py-1 border rounded bg-gray-200 text-gray-400 mr-2">
                Previous
              </button>
              <button disabled className="px-3 py-1 border rounded bg-gray-200 text-gray-400">
                Next
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DeploymentHistory;
