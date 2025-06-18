import React, { useState, useEffect } from 'react';
import { Credential, CreateCredentialDto, UpdateCredentialDto, CredentialType } from '../types/credentials';
import credentialsService from '../services/credentialsService';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import CredentialModal from '../components/credentials/CredentialModal';
import CredentialItem from '../components/credentials/CredentialItem';

const CredentialsManagement: React.FC = () => {
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalData, setModalData] = useState<{
    type: 'create' | 'edit';
    data?: Partial<CreateCredentialDto>;
    id?: number;
  }>({ type: 'create' });
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<{show: boolean, id?: number}>({
    show: false
  });

  // Fetch credentials on component mount
  useEffect(() => {
    fetchCredentials();
  }, []);

  const fetchCredentials = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await credentialsService.getAll();
      console.log('Credential data:', data);
      setCredentials(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Error fetching credentials:', err);
      setError(`Gagal memuat data kredensial: ${err.response?.data?.detail || err.message || 'Silakan coba lagi.'}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCredential = async (data: CreateCredentialDto) => {
    try {
      setModalLoading(true);
      await credentialsService.create(data);
      setShowModal(false);
      await fetchCredentials();
    } catch (err: any) {
      console.error('Error creating credential:', err);
      
      // Menangani berbagai format error
      let errorMessage = 'Silakan coba lagi.';
      if (err.response?.data) {
        if (typeof err.response.data === 'string') {
          errorMessage = err.response.data;
        } else if (err.response.data.detail) {
          // Handle detail yang bisa berupa string atau array
          if (typeof err.response.data.detail === 'string') {
            errorMessage = err.response.data.detail;
          } else if (Array.isArray(err.response.data.detail)) {
            errorMessage = err.response.data.detail.map((item: any) => 
              `${item.loc ? item.loc.join('.') + ': ' : ''}${item.msg}`
            ).join('\n');
          } else {
            errorMessage = JSON.stringify(err.response.data.detail);
          }
        } else if (typeof err.response.data === 'object') {
          errorMessage = Object.entries(err.response.data)
            .map(([key, value]) => `${key}: ${value}`)
            .join('\n');
        }
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(`Gagal menambahkan kredensial: ${errorMessage}`);
    } finally {
      setModalLoading(false);
    }
  };

  const handleUpdateCredential = async (data: CreateCredentialDto) => {
    try {
      if (!modalData.id) return;
      
      setModalLoading(true);
      await credentialsService.update(modalData.id, data as UpdateCredentialDto);
      setShowModal(false);
      await fetchCredentials();
    } catch (err: any) {
      console.error('Error updating credential:', err);
      setError(`Gagal memperbarui kredensial: ${err.response?.data?.detail || 'Silakan coba lagi.'}`);
    } finally {
      setModalLoading(false);
    }
  };

  const handleDeleteCredential = async () => {
    try {
      if (!showDeleteConfirm.id) return;
      
      setLoading(true);
      await credentialsService.delete(showDeleteConfirm.id);
      setShowDeleteConfirm({show: false});
      await fetchCredentials();
    } catch (err: any) {
      console.error('Error deleting credential:', err);
      setError(`Gagal menghapus kredensial: ${err.response?.data?.detail || 'Silakan coba lagi.'}`);
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setModalData({ type: 'create' });
    setShowModal(true);
  };

  const openEditModal = (credential: Credential) => {
    // Prepare the data for the modal, matching the expected format
    // For AWS credentials
    let formData: Partial<CreateCredentialDto> = {
      name: credential.name,
      type: credential.type as CredentialType
    };
    
    // Note: The server doesn't return sensitive data, 
    // so backend would need an API to fetch decrypted credentials for editing
    
    setModalData({
      type: 'edit',
      data: formData,
      id: credential.id
    });
    setShowModal(true);
  };

  const openDeleteConfirm = (id: number) => {
    setShowDeleteConfirm({show: true, id});
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Manajemen Kredensial</h1>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            onClick={fetchCredentials}
            isLoading={loading}
            className="mr-2"
          >
            <span className="flex items-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Muat Ulang
            </span>
          </Button>
          <Button variant="success" onClick={openCreateModal}>
            Tambah Kredensial Baru
          </Button>
        </div>
      </div>
      
      <Card className="mb-6 p-6">
        <h2 className="text-xl font-semibold mb-4">Kredensial Cloud Provider</h2>
        <p className="text-gray-600 mb-4">
          Kelola kredensial Anda untuk berbagai provider cloud seperti AWS, Google Cloud, dan lainnya.
          Kredensial ini diperlukan untuk mengakses API cloud provider dan membuat virtual machine.
        </p>
      </Card>
      
      {error && (
        <div className="p-4 mb-4 border border-red-200 rounded-md bg-red-50">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="font-medium text-red-800 mb-1">Error:</p>
              <pre className="whitespace-pre-wrap text-sm text-red-600">{error}</pre>
            </div>
            <div className="ml-auto pl-3">
              <div className="-mx-1.5 -my-1.5">
                <button
                  onClick={() => setError('')}
                  className="inline-flex rounded-md p-1.5 text-red-500 hover:bg-red-100 focus:outline-none"
                >
                  <span className="sr-only">Dismiss</span>
                  <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Nama
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Dibuat Pada
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Aksi
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500" colSpan={4}>
                    <div className="flex justify-center">
                      <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-500"></div>
                    </div>
                  </td>
                </tr>
              ) : credentials.length === 0 ? (
                <tr>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500" colSpan={4}>
                    Belum ada kredensial. Klik "Tambah Kredensial Baru" untuk memulai.
                  </td>
                </tr>
              ) : (
                credentials.map(credential => (
                  <CredentialItem
                    key={credential.id}
                    credential={credential}
                    onEdit={openEditModal}
                    onDelete={openDeleteConfirm}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
      
      {/* Create/Edit Modal */}
      <CredentialModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSubmit={modalData.type === 'create' ? handleCreateCredential : handleUpdateCredential}
        initialData={modalData.data}
        isLoading={modalLoading}
        title={modalData.type === 'create' ? 'Tambah Kredensial Baru' : 'Edit Kredensial'}
      />
      
      {/* Delete Confirmation Modal */}
      {showDeleteConfirm.show && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-md p-6">
            <h2 className="text-xl font-bold mb-4">Konfirmasi Hapus</h2>
            <p className="text-gray-700 mb-6">
              Apakah Anda yakin ingin menghapus kredensial ini? Tindakan ini tidak dapat dibatalkan.
            </p>
            <div className="flex justify-end space-x-3">
              <Button
                variant="outline"
                onClick={() => setShowDeleteConfirm({show: false})}
              >
                Batal
              </Button>
              <Button
                variant="danger"
                onClick={handleDeleteCredential}
                isLoading={loading}
              >
                Hapus
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default CredentialsManagement;
