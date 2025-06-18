import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import terraformService from '../services/terraformService';
import vmService from '../services/vmService';
import { toast } from 'react-hot-toast';
import { SSHButton } from '../components/SSHButton';

interface VMDetails {
  id: string;
  name: string;
  provider: string;
  region: string;
  zone?: string;
  instance_id?: string;
  status: string;
  public_ip: string | null;
  private_ip: string | null;
  created_at?: string;
  updated_at?: string;
  preset?: string;
  credential_id?: number;
  instance_type?: string;
  metadata?: any;
}

const VMDetails: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [vm, setVM] = useState<VMDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVMDetails = async () => {
      if (!id) return;
      
      try {
        setLoading(true);
        setError(null);
        
        // Fetch VM details using the vmService
        const response = await terraformService.getDeploymentStatus(parseInt(id));
        setVM(response);
      } catch (err: any) {
        console.error('Error fetching VM details:', err);
        setError(`Gagal memuat detail VM: ${err.message}`);
        toast.error(`Gagal memuat detail VM: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };

    fetchVMDetails();
  }, [id]);

  const handleStartVM = async () => {
    if (!vm) return;
    
    try {
      toast.loading('Memulai VM...', { id: 'start-vm' });
      await terraformService.startVM(parseInt(vm.id));
      toast.success('VM berhasil dimulai', { id: 'start-vm' });
      
      // Refresh VM details
      const updatedVM = await terraformService.getDeploymentStatus(parseInt(vm.id));
      setVM(updatedVM);
    } catch (err: any) {
      console.error('Error starting VM:', err);
      toast.error(`Gagal memulai VM: ${err.message}`, { id: 'start-vm' });
    }
  };

  const handleStopVM = async () => {
    if (!vm) return;
    
    try {
      toast.loading('Menghentikan VM...', { id: 'stop-vm' });
      await terraformService.stopVM(parseInt(vm.id));
      toast.success('VM berhasil dihentikan', { id: 'stop-vm' });
      
      // Refresh VM details
      const updatedVM = await terraformService.getDeploymentStatus(parseInt(vm.id));
      setVM(updatedVM);
    } catch (err: any) {
      console.error('Error stopping VM:', err);
      toast.error(`Gagal menghentikan VM: ${err.message}`, { id: 'stop-vm' });
    }
  };

  const handleDeleteVM = async () => {
    if (!vm) return;
    
    if (window.confirm('Apakah Anda yakin ingin menghapus VM ini?')) {
      try {
        toast.loading('Menghapus VM...', { id: 'delete-vm' });
        await terraformService.deleteVM(parseInt(vm.id));
        toast.success('VM berhasil dihapus', { id: 'delete-vm' });
        
        // Navigate back to dashboard
        navigate('/dashboard');
      } catch (err: any) {
        console.error('Error deleting VM:', err);
        toast.error(`Gagal menghapus VM: ${err.message}`, { id: 'delete-vm' });
      }
    }
  };

  const getStatusColor = (status: string) => {
    status = status.toLowerCase();
    if (status.includes('running')) return 'bg-green-100 text-green-800';
    if (status.includes('stopped')) return 'bg-yellow-100 text-yellow-800';
    if (status.includes('pending') || status.includes('provisioning')) return 'bg-blue-100 text-blue-800';
    if (status.includes('error') || status.includes('failed')) return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleString();
  };

  const getProviderIcon = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'gcp':
        return (
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 11.1L9.3 7.1H6L12 17.5L18 7.1H14.7L12 11.1Z" fill="#EA4335" />
            <path d="M18 7.1H14.7L12 11.1L9.3 7.1H6L4.8 9.1L12 17.5L18 7.1Z" fill="#4285F4" />
            <path d="M4.8 9.1L12 17.5L6 7.1H4.8V9.1Z" fill="#34A853" />
          </svg>
        );
      case 'aws':
        return (
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M9.9 15.6L8.2 14.5V9.5L9.9 8.4L11.6 9.5V14.5L9.9 15.6Z" fill="#F90" />
            <path d="M14.1 15.6L12.4 14.5V9.5L14.1 8.4L15.8 9.5V14.5L14.1 15.6Z" fill="#F90" />
            <path d="M12 6L13.7 7.1L12 8.2L10.3 7.1L12 6Z" fill="#F90" />
            <path d="M12 17.9L10.3 16.8L12 15.7L13.7 16.8L12 17.9Z" fill="#F90" />
          </svg>
        );
      default:
        return (
          <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="4" y="4" width="16" height="16" rx="2" fill="#CBD5E0" />
            <path d="M12 8V16M8 12H16" stroke="#4A5568" strokeWidth="2" strokeLinecap="round" />
          </svg>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        <p>{error}</p>
        <button 
          onClick={() => navigate('/dashboard')}
          className="mt-2 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
        >
          Kembali ke Dashboard
        </button>
      </div>
    );
  }

  if (!vm) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded">
        <p>VM tidak ditemukan</p>
        <button 
          onClick={() => navigate('/dashboard')}
          className="mt-2 px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700"
        >
          Kembali ke Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">{vm.name}</h1>
          <p className="text-gray-500">ID: {vm.id}</p>
        </div>
        <div className="flex space-x-2">
          <button 
            onClick={() => navigate('/dashboard')}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Kembali
          </button>
          {vm.status.toLowerCase().includes('running') ? (
            <button 
              onClick={handleStopVM}
              className="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600"
            >
              Stop VM
            </button>
          ) : vm.status.toLowerCase().includes('stopped') ? (
            <button 
              onClick={handleStartVM}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
            >
              Start VM
            </button>
          ) : null}
          <button 
            onClick={handleDeleteVM}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Delete VM
          </button>
          {vm.status.toLowerCase().includes('running') && (
            <SSHButton
              vmId={parseInt(vm.id)}
              vmName={vm.name}
              isRunning={vm.status.toLowerCase().includes('running')}
            />
          )}
        </div>
      </div>

      <div className="bg-white shadow-md rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-800">Informasi VM</h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-500">Status</h3>
              <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(vm.status)}`}>
                {vm.status}
              </span>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-gray-500">Provider</h3>
              <div className="flex items-center mt-1">
                {getProviderIcon(vm.provider)}
                <span className="ml-2 text-gray-800">{vm.provider.toUpperCase()}</span>
              </div>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-gray-500">Region</h3>
              <p className="text-gray-800">{vm.region}</p>
            </div>
            
            {vm.zone && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Zone</h3>
                <p className="text-gray-800">{vm.zone}</p>
              </div>
            )}
            
            {vm.instance_type && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Instance Type</h3>
                <p className="text-gray-800">{vm.instance_type}</p>
              </div>
            )}
            
            {vm.preset && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Preset</h3>
                <p className="text-gray-800">{vm.preset.replace('_', ' ')}</p>
              </div>
            )}
          </div>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-gray-500">Public IP</h3>
              <p className="text-gray-800">{vm.public_ip || '—'}</p>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-gray-500">Private IP</h3>
              <p className="text-gray-800">{vm.private_ip || '—'}</p>
            </div>
            
            {vm.instance_id && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Instance ID</h3>
                <p className="text-gray-800 break-all">{vm.instance_id}</p>
              </div>
            )}
            
            {vm.created_at && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Created At</h3>
                <p className="text-gray-800">{formatDate(vm.created_at)}</p>
              </div>
            )}
            
            {vm.updated_at && (
              <div>
                <h3 className="text-sm font-medium text-gray-500">Last Updated</h3>
                <p className="text-gray-800">{formatDate(vm.updated_at)}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Metadata section (if available) */}
      {vm.metadata && Object.keys(vm.metadata).length > 0 && (
        <div className="bg-white shadow-md rounded-lg overflow-hidden mt-6">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-800">Metadata</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(vm.metadata).map(([key, value]) => (
                <div key={key}>
                  <h3 className="text-sm font-medium text-gray-500">{key}</h3>
                  <p className="text-gray-800 break-all">{String(value)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VMDetails;
