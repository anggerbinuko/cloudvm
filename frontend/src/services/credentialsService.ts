import http from './httpService';
import { Credential, UpdateCredentialDto } from '../types/credentials';

interface CredentialListResponse {
  credentials: Credential[];
  total: number;
}

const credentialsService = {
  getAll: async (): Promise<Credential[]> => {
    try {
      const response = await http.get<CredentialListResponse>('/api/v1/credentials/credentials/');
      // Sesuaikan dengan format respons API backend
      console.log('Credential response:', response.data);
      return response.data.credentials || [];
    } catch (error) {
      console.error('Error getting all credentials:', error);
      throw error;
    }
  },

  getById: async (id: number): Promise<Credential> => {
    const response = await http.get<Credential>(`/api/v1/credentials/credentials/${id}`);
    return response.data;
  },

  create: async (data: any): Promise<Credential> => {
    try {
      console.log('Sending data to create credential:', data);
      
      // Tidak perlu memformat data GCP lagi karena sudah diformat dengan benar di CredentialForm.tsx
      // Hanya log untuk debugging
      if (data.type === 'gcp' && data.gcp_credentials) {
        console.log('GCP credential data detected');
        console.log('service_account_key type:', typeof data.gcp_credentials.service_account_key);
        
        if (data.gcp_credentials.service_account_key) {
          if (typeof data.gcp_credentials.service_account_key === 'string') {
            console.warn('WARNING: service_account_key is a string, should be an object');
          } else {
            console.log('service_account_key is an object with keys:', 
              Object.keys(data.gcp_credentials.service_account_key));
          }
        }
      }
      
      console.log('Sending final data to API (stringified for log):', 
        JSON.stringify(data, (key, value) => 
          // Mask sensitive info in logs
          key === 'private_key' ? '[MASKED]' : value
        , 2)
      );
      
      const response = await http.post<Credential>('/api/v1/credentials/credentials/', data);
      console.log('Response from create credential:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('Error in create credential service:', error);
      if (error.response) {
        console.error('Error response status:', error.response.status);
        console.error('Error response data:', error.response.data);
        console.error('Error response headers:', error.response.headers);
      }
      throw error;
    }
  },

  update: async (id: number, data: UpdateCredentialDto): Promise<Credential> => {
    const response = await http.put<Credential>(`/api/v1/credentials/credentials/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await http.delete(`/api/v1/credentials/credentials/${id}`);
  },
  
  validate: async (id: number): Promise<{valid: boolean; message: string}> => {
    const response = await http.get<{valid: boolean; message: string}>(`/api/v1/credentials/credentials/${id}/validate`);
    return response.data;
  },
  
  getDetails: async (id: number): Promise<any> => {
    const response = await http.get<any>(`/api/v1/credentials/credentials/${id}/details`);
    return response.data;
  },
  
  uploadGcpJson: async (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      console.log(`Uploading GCP JSON file: ${file.name} (${file.size} bytes)`);
      
      // Gunakan metode upload khusus untuk FormData
      const response = await http.upload('/api/v1/credentials/credentials/upload-gcp-json', formData);
      
      console.log('GCP JSON upload successful, response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('Error uploading GCP JSON:', error);
      if (error.response) {
        console.error('Error response status:', error.response.status);
        console.error('Error response data:', error.response.data);
      }
      throw error;
    }
  }
};

export default credentialsService; 