import React from 'react';
import { CreateCredentialDto } from '../../types/credentials';
import CredentialForm from './CredentialForm';
import Card from '../common/Card';

interface CredentialModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: CreateCredentialDto) => Promise<void>;
  initialData?: Partial<CreateCredentialDto>;
  isLoading: boolean;
  title: string;
}

const CredentialModal: React.FC<CredentialModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  isLoading,
  title
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-auto" onClick={e => e.stopPropagation()}>
        <Card className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-bold">{title}</h2>
            <button 
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700"
              disabled={isLoading}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <CredentialForm 
            initialData={initialData}
            onSubmit={onSubmit}
            onCancel={onClose}
            isLoading={isLoading}
          />
        </Card>
      </div>
    </div>
  );
};

export default CredentialModal; 