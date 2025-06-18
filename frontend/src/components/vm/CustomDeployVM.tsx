import React from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../common/Button';

const CustomDeployVM: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">Custom VM Deployment</h1>
      <p className="text-gray-600 mb-6">Konfigurasi lengkap untuk virtual machine Anda</p>

      {/* Placeholder untuk form konfigurasi lengkap */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="text-center py-12">
          <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <h2 className="text-xl font-medium mb-4">Custom VM Deployment</h2>
          <p className="text-gray-500 mb-6">
            Fitur kustomisasi lengkap sedang dalam pengembangan. 
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

export default CustomDeployVM;
