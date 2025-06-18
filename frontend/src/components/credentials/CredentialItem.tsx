import React, { useState } from 'react';
import { Credential, providerFields } from '../../types/credentials';
import Button from '../common/Button';
import credentialsService from '../../services/credentialsService';

interface CredentialItemProps {
  credential: Credential;
  onEdit: (credential: Credential) => void;
  onDelete: (credentialId: number) => void;
}

const CredentialItem: React.FC<CredentialItemProps> = ({ credential, onEdit, onDelete }) => {
  const [validationStatus, setValidationStatus] = useState<{
    isValid: boolean | null;
    message: string;
    loading: boolean;
  }>({
    isValid: null,
    message: '',
    loading: false
  });

  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return '-';
    
    try {
      const date = new Date(dateString);
      return new Intl.DateTimeFormat('id-ID', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      }).format(date);
    } catch (error) {
      console.error('Error formatting date:', error);
      return dateString; // Kembalikan string asli jika format gagal
    }
  };

  const getProviderLabel = (type: string) => {
    return providerFields[type as keyof typeof providerFields]?.label || type;
  };

  const handleTestCredential = async () => {
    try {
      setValidationStatus({
        isValid: null,
        message: '',
        loading: true
      });
      
      const result = await credentialsService.validate(credential.id);
      
      setValidationStatus({
        isValid: result.valid,
        message: result.message,
        loading: false
      });
      
      // Reset validation status after 5 seconds
      setTimeout(() => {
        setValidationStatus({
          isValid: null,
          message: '',
          loading: false
        });
      }, 5000);
      
    } catch (error: any) {
      console.error('Error validating credential:', error);
      setValidationStatus({
        isValid: false,
        message: error.response?.data?.detail || 'Gagal memvalidasi kredensial',
        loading: false
      });
      
      // Reset validation status after 5 seconds
      setTimeout(() => {
        setValidationStatus({
          isValid: null,
          message: '',
          loading: false
        });
      }, 5000);
    }
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm font-medium text-gray-900">{credential.name || 'Tanpa Nama'}</div>
        {validationStatus.isValid !== null && (
          <div className={`mt-1 text-xs font-medium ${
            validationStatus.isValid ? 'text-green-600' : 'text-red-600'
          }`}>
            {validationStatus.isValid ? 'Kredensial Valid' : 'Kredensial Tidak Valid'} 
            {validationStatus.message && `: ${validationStatus.message}`}
          </div>
        )}
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-900">{getProviderLabel(credential.type)}</div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap">
        <div className="text-sm text-gray-500">{formatDate(credential.created_at)}</div>
      </td>
      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
        <div className="flex justify-left space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTestCredential}
            isLoading={validationStatus.loading}
          >
            Test
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onEdit(credential)}
          >
            Edit
          </Button>
          <Button
            variant="danger"
            size="sm"
            onClick={() => onDelete(credential.id)}
          >
            Hapus
          </Button>
        </div>
      </td>
    </tr>
  );
};

export default CredentialItem; 