import http from './httpService';

export interface VM {
  id: string;
  name: string;
  cloud_provider: 'AWS' | 'Azure' | 'GCP';
  instance_type: string;
  status: 'running' | 'stopped' | 'terminated';
  ip_address?: string;
  created_at: string;
}

const vmService = {
  getAllVMs: async (): Promise<VM[]> => {
    const response = await http.get<VM[]>('/api/v1/vms/vms');
    return response.data;
  },
  
  getVM: async (id: string): Promise<VM> => {
    const response = await http.get<VM>(`/api/v1/vms/vms/${id}`);
    return response.data;
  },
  
  createVM: async (vmData: Partial<VM>): Promise<VM> => {
    const response = await http.post<VM>('/api/v1/vms/vms', vmData);
    return response.data;
  },
  
  updateVM: async (id: string, vmData: Partial<VM>): Promise<VM> => {
    const response = await http.put<VM>(`/api/v1/vms/vms/${id}`, vmData);
    return response.data;
  },
  
  deleteVM: async (id: string): Promise<void> => {
    await http.delete(`/api/v1/vms/vms/${id}`);
  },
}

export default vmService;