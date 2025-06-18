import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../common/Button';

const MultiDeployVM: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">Multi-VM Deployment</h1>
      <p className="text-gray-600 mb-6">Deploy beberapa virtual machine sekaligus</p>

      {/* Placeholder untuk form multi deployment */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7c-2 0-3 1-3 3z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 11v6M9 5v2M15 11v6M15 5v2M9 11h6M9 5h6" />
            </svg>
          </div>
          <h2 className="text-xl font-medium mb-4">Multi-VM Deployment</h2>
          <p className="text-gray-500 mb-6">
            Fitur deployment multi VM sedang dalam pengembangan.
            <br />
            Silakan gunakan Quick Deploy untuk saat ini.
          </p>
          <div className="flex justify-center">
            <Button
              variant="primary"
              onClick={() => navigate('/create-vm')}
            >
              Kembali ke Menu Utama
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MultiDeployVM;
