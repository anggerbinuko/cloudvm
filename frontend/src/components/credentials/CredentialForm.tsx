import React, { useState, useRef } from 'react';
import { 
  CreateCredentialDto, 
  CredentialType, 
  AWSCredentials, 
  GCPCredentials, 
  providerFields,
} from '../../types/credentials';
import Input from '../forms/Input';
import Button from '../common/Button';
import http from '../../services/httpService';

// Daftar region AWS
const AWS_REGIONS = [
  { value: 'us-east-1', label: 'US East (N. Virginia)' },
  { value: 'us-east-2', label: 'US East (Ohio)' },
  { value: 'us-west-1', label: 'US West (N. California)' },
  { value: 'us-west-2', label: 'US West (Oregon)' },
  { value: 'af-south-1', label: 'Africa (Cape Town)' },
  { value: 'ap-east-1', label: 'Asia Pacific (Hong Kong)' },
  { value: 'ap-south-1', label: 'Asia Pacific (Mumbai)' },
  { value: 'ap-northeast-3', label: 'Asia Pacific (Osaka)' },
  { value: 'ap-northeast-2', label: 'Asia Pacific (Seoul)' },
  { value: 'ap-southeast-1', label: 'Asia Pacific (Singapore)' },
  { value: 'ap-southeast-2', label: 'Asia Pacific (Sydney)' },
  { value: 'ap-northeast-1', label: 'Asia Pacific (Tokyo)' },
  { value: 'ca-central-1', label: 'Canada (Central)' },
  { value: 'eu-central-1', label: 'Europe (Frankfurt)' },
  { value: 'eu-west-1', label: 'Europe (Ireland)' },
  { value: 'eu-west-2', label: 'Europe (London)' },
  { value: 'eu-south-1', label: 'Europe (Milan)' },
  { value: 'eu-west-3', label: 'Europe (Paris)' },
  { value: 'eu-north-1', label: 'Europe (Stockholm)' },
  { value: 'me-south-1', label: 'Middle East (Bahrain)' },
  { value: 'sa-east-1', label: 'South America (São Paulo)' },
];

interface CredentialFormProps {
  initialData?: Partial<CreateCredentialDto>;
  onSubmit: (data: any) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

const CredentialForm: React.FC<CredentialFormProps> = ({
  initialData = { name: '', type: 'aws' },
  onSubmit,
  onCancel,
  isLoading
}) => {
  const [formData, setFormData] = useState<CreateCredentialDto>({
    name: initialData.name || '',
    type: initialData.type || 'aws',
    aws_credentials: initialData.aws_credentials || { access_key: '', secret_key: '', region: '' },
    gcp_credentials: initialData.gcp_credentials || { 
      project_id: '', 
      private_key_id: '', 
      private_key: '', 
      client_email: '', 
      client_id: '' 
    }
  });
  
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [uploadLoading, setUploadLoading] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!formData.name.trim()) {
      newErrors.name = 'Nama kredensial harus diisi';
    }
    
    const type = formData.type as CredentialType;
    const fieldDef = providerFields[type];
    
    if (type === 'aws') {
      if (!formData.aws_credentials?.access_key?.trim()) {
        newErrors['aws_credentials.access_key'] = 'Access key harus diisi';
      }
      
      if (!formData.aws_credentials?.secret_key?.trim()) {
        newErrors['aws_credentials.secret_key'] = 'Secret key harus diisi';
      }
      
      if (!formData.aws_credentials?.region?.trim()) {
        newErrors['aws_credentials.region'] = 'Region harus diisi';
      }
    } else if (type === 'gcp') {
      // Jika file sudah diupload, tidak perlu validasi lagi
      if (uploadStatus.includes('berhasil') && formData.uploadedGcpData) {
        // File JSON sudah diupload, tidak perlu validasi field
        return true;
      }
      
      // Jika belum ada file yang diupload, tampilkan error
      newErrors.fileUpload = 'Mohon upload file JSON kredensial GCP terlebih dahulu';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const formatErrorMessage = (error: any): string => {
    // Set error message
    let errorMessage = 'Terjadi kesalahan saat mengirim form.';
    
    if (error.response?.data) {
      console.log('Error data type:', typeof error.response.data);
      console.log('Error data:', error.response.data);
      
      if (typeof error.response.data === 'string') {
        errorMessage = error.response.data;
      } else if (error.response.data.detail) {
        // Handle detail yang bisa berupa string atau array
        if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map((item: any) => 
            `${item.loc ? item.loc.join('.') + ': ' : ''}${item.msg}`
          ).join('\n');
        } else {
          errorMessage = JSON.stringify(error.response.data.detail);
        }
      } else if (typeof error.response.data === 'object') {
        errorMessage = Object.entries(error.response.data)
          .map(([key, value]) => `${key}: ${value}`)
          .join('\n');
      }
    } else if (error.message) {
      errorMessage = error.message;
    }
    
    return errorMessage;
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (validate()) {
      try {
        // Konversi format data sesuai dengan API backend
        if (formData.type === 'aws') {
          // Format untuk AWS
          const awsData = {
            name: formData.name,
            type: 'aws',
            aws_credentials: {
              name: formData.name,  // Add name field to aws_credentials
              access_key: formData.aws_credentials?.access_key || '',
              secret_key: formData.aws_credentials?.secret_key || '',
              region: formData.aws_credentials?.region || ''
            }
          };
          console.log('Submitting AWS credential:', awsData);
          await onSubmit(awsData);
        } else if (formData.type === 'gcp') {
          // Jika menggunakan data dari upload file JSON
          if (formData.uploadedGcpData && uploadStatus.includes('berhasil')) {
            console.log('Using uploaded GCP data with keys:', Object.keys(formData.uploadedGcpData));
            
            // Verifikasi tipe data service_account_key untuk logging
            let serviceAccountKey = formData.uploadedGcpData.service_account_key;
            if (serviceAccountKey) {
              console.log('Service account key type:', typeof serviceAccountKey);
              
              if (typeof serviceAccountKey === 'object') {
                console.log('Service account key has keys:', Object.keys(serviceAccountKey));
              }
            }
            
            // Format data untuk submit kredensial
            // Struktur yang diharapkan oleh backend adalah:
            // {
            //   "name": string,
            //   "type": "gcp",
            //   "gcp_credentials": {
            //     "gcp_project_id": string,
            //     "gcp_service_account_json": object
            //   }
            // }
            const gcpData = {
              name: formData.name,
              type: 'gcp',
              gcp_credentials: {
                gcp_project_id: formData.uploadedGcpData.project_id || '',
                gcp_service_account_json: serviceAccountKey
              }
            };
            
            console.log('Submitting GCP credential with data structure:', {
              name: gcpData.name,
              type: gcpData.type,
              'gcp_credentials.gcp_project_id': gcpData.gcp_credentials.gcp_project_id,
              service_account_key_type: typeof gcpData.gcp_credentials.gcp_service_account_json,
              service_account_key_exists: !!gcpData.gcp_credentials.gcp_service_account_json
            });

            await onSubmit(gcpData);
          } else {
            // Jika tidak ada file yang diupload, tampilkan error
            setErrors({
              ...errors,
              fileUpload: 'Mohon upload file JSON kredensial GCP terlebih dahulu'
            });
            setUploadStatus('Mohon upload file terlebih dahulu');
            return;
          }
        }
      } catch (error: any) {
        console.error('Error submitting form:', error);
        
        // Log detail error untuk debugging
        if (error.response) {
          console.error('Submit error response:', error.response.status, error.response.data);
          
          // Log detail error untuk detail array
          if (error.response.data && error.response.data.detail && Array.isArray(error.response.data.detail)) {
            console.error('Validation errors:');
            error.response.data.detail.forEach((err: any, index: number) => {
              console.error(`Error ${index + 1}:`, err);
            });
          }
        }
        
        // Set error message
        const errorMessage = formatErrorMessage(error);
        
        setErrors({
          ...errors,
          submit: errorMessage
        });
      }
    }
  };
  
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    
    if (name === 'type' && value !== formData.type) {
      // Reset upload status when switching credential type
      setUploadStatus('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
    
    if (name.startsWith('aws_credentials.')) {
      const field = name.split('.')[1];
      setFormData(prev => ({
        ...prev,
        aws_credentials: {
          ...prev.aws_credentials as AWSCredentials,
          [field]: value
        }
      }));
    } else if (name.startsWith('gcp_credentials.')) {
      const field = name.split('.')[1];
      setFormData(prev => ({
        ...prev,
        gcp_credentials: {
          ...prev.gcp_credentials as GCPCredentials,
          [field]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [name]: value
      }));
    }
  };
  
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Validasi tipe file
    if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
      setErrors({...errors, fileUpload: 'File harus berformat JSON'});
      return;
    }
    
    try {
      setUploadLoading(true);
      setUploadStatus('Mengupload file...');
      
      const formData = new FormData();
      formData.append('file', file);
      
      console.log(`Uploading file: ${file.name} (${file.size} bytes)`);
      
      // Gunakan http.upload khusus untuk form-data daripada http.post
      const response = await http.upload('/api/v1/credentials/credentials/upload-gcp-json', formData);
      
      // Log respons untuk debugging
      console.log('Upload Response Status:', response.status);
      console.log('GCP JSON upload response:', response.data);
      
      if (response.data && response.data.data) {
        // Log struktur data untuk debugging
        console.log('Response data keys:', Object.keys(response.data.data));
        console.log('Service account key exists:', !!response.data.data.gcp_service_account_json);
        console.log('Service account key type:', typeof response.data.data.gcp_service_account_json);
        
        // Pastikan service_account_key adalah objek
        let serviceAccountKey = response.data.data.gcp_service_account_json;
        if (typeof serviceAccountKey === 'string') {
          try {
            console.log('Converting service_account_key from string to object');
            serviceAccountKey = JSON.parse(serviceAccountKey);
          } catch (e) {
            console.error('Error parsing service_account_key:', e);
            setErrors({...errors, fileUpload: 'Format service_account_key tidak valid'});
            setUploadStatus('Gagal memproses file: format service_account_key tidak valid');
            setUploadLoading(false);
            return;
          }
        }
        
        // Default value untuk setiap field yang diperlukan
        const defaultGcpValues: GCPCredentials = {
          project_id: '',
          private_key_id: '',
          private_key: '',
          client_email: '',
          client_id: ''
        };
        
        // Simpan data dari respons API untuk digunakan saat form disubmit
        setFormData(prev => ({
          ...prev,
          name: prev.name || 'GCP Credential', // Default name jika kosong
          uploadedGcpData: {
            service_account_key: serviceAccountKey,
            project_id: response.data.data.gcp_project_id || ''
          },
          gcp_credentials: {
            ...defaultGcpValues,
            project_id: response.data.data.gcp_project_id || defaultGcpValues.project_id
          }
        }));
        
        setUploadStatus('File berhasil diupload');
        // Hapus error jika ada
        const newErrors = {...errors};
        delete newErrors.fileUpload;
        setErrors(newErrors);
      } else {
        console.error('Invalid response format:', response.data);
        setErrors({...errors, fileUpload: 'Format respons server tidak valid'});
        setUploadStatus('Gagal mengupload file: format tidak valid');
      }
    } catch (error: any) {
      console.error('Error uploading GCP JSON file:', error);
      
      // Log detail error untuk debugging
      if (error.response) {
        console.error('Error response:', error.response.status, error.response.data);
        setErrors({
          ...errors, 
          fileUpload: `Gagal mengupload file: ${error.response.status} - ${error.response.data?.detail || JSON.stringify(error.response.data) || 'Not Found'}`
        });
      } else if (error.request) {
        console.error('No response received:', error.request);
        setErrors({
          ...errors, 
          fileUpload: 'Gagal mengupload file: Tidak ada respons dari server'
        });
      } else {
        console.error('Error message:', error.message);
        setErrors({
          ...errors, 
          fileUpload: `Gagal mengupload file: ${error.message}`
        });
      }
      
      setUploadStatus('Gagal mengupload file');
    } finally {
      setUploadLoading(false);
    }
  };
  
  const renderCredentialFields = () => {
    const type = formData.type as CredentialType;
    const provider = providerFields[type];
    
    if (!provider) return null;
    
    if (type === 'aws') {
      return (
        <>
          <div className="mb-3">
            <Input
              id="aws_credentials.access_key"
              name="aws_credentials.access_key"
              label="Access Key"
              placeholder="Masukkan AWS Access Key"
              value={(formData.aws_credentials as AWSCredentials)?.access_key || ''}
              onChange={handleChange}
              error={errors[`aws_credentials.access_key`]}
              type="password"
              required
            />
          </div>
          <div className="mb-3">
            <Input
              id="aws_credentials.secret_key"
              name="aws_credentials.secret_key"
              label="Secret Key"
              placeholder="Masukkan AWS Secret Key"
              value={(formData.aws_credentials as AWSCredentials)?.secret_key || ''}
              onChange={handleChange}
              error={errors[`aws_credentials.secret_key`]}
              type="password"
              required
            />
          </div>
          <div className="mb-3">
            <label htmlFor="aws_credentials.region" className="block text-sm font-medium text-gray-700 mb-1">
              Region
            </label>
            <select
              id="aws_credentials.region"
              name="aws_credentials.region"
              value={(formData.aws_credentials as AWSCredentials)?.region || ''}
              onChange={handleChange}
              className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              required
            >
              <option value="" disabled>Pilih AWS Region</option>
              {AWS_REGIONS.map(region => (
                <option key={region.value} value={region.value}>
                  {region.label}
                </option>
              ))}
            </select>
            {errors[`aws_credentials.region`] && (
              <p className="mt-1 text-sm text-red-600">{errors[`aws_credentials.region`]}</p>
            )}
          </div>
        </>
      );
    } else if (type === 'gcp') {
      return (
        <>
          <div className="mb-3">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Upload File Kredensial JSON
            </label>
            <div className="flex flex-col space-y-2">
              <p className="text-sm text-gray-600 mb-2">
                Upload file credentials.json dari Google Cloud Console untuk mengisi otomatis semua field.
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,application/json"
                onChange={handleFileUpload}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
              {uploadLoading && <p className="text-sm text-blue-600">Sedang mengupload...</p>}
              {uploadStatus && !uploadLoading && (
                <p className={`text-sm ${uploadStatus.includes('berhasil') ? 'text-green-600' : 'text-red-600'}`}>
                  {uploadStatus}
                </p>
              )}
              {errors.fileUpload && <p className="text-sm text-red-600">{errors.fileUpload}</p>}
            </div>
          </div>
        </>
      );
    }
    
    return null;
  };
  
  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        id="name"
        name="name"
        label="Nama Kredensial"
        placeholder="Masukkan nama kredensial"
        value={formData.name}
        onChange={handleChange}
        error={errors.name}
        required
      />
      
      <div className="w-full">
        <label htmlFor="type" className="block text-sm font-medium text-gray-700 mb-1">
          Provider
        </label>
        <select
          id="type"
          name="type"
          value={formData.type}
          onChange={handleChange}
          className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
        >
          {Object.entries(providerFields).map(([key, { label }]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </div>
      
      <div className="border-t border-gray-200 pt-4 mt-4">
        <h3 className="text-lg font-medium mb-3">Informasi Kredensial</h3>
        {renderCredentialFields()}
      </div>
      
      {errors.submit && (
        <div className="p-3 mb-3 bg-red-50 border border-red-200 rounded-md">
          <p className="font-medium text-red-800 mb-1">Error:</p>
          <pre className="whitespace-pre-wrap text-sm text-red-600">{errors.submit}</pre>
        </div>
      )}
      
      <div className="flex justify-end space-x-3 pt-4">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isLoading}
        >
          Batal
        </Button>
        <Button
          type="submit"
          variant="primary"
          isLoading={isLoading}
        >
          Simpan
        </Button>
      </div>
    </form>
  );
};

export default CredentialForm; 