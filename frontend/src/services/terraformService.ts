import http from './httpService';
import API_BASE_URL, { TOKEN_KEY } from '../config';
import axios from 'axios';

// Interface untuk data permintaan deployment VM
export interface VMDeploymentRequest {
  name: string;
  provider: string;
  region: string;
  zone?: string; // Tambahkan zone sebagai field opsional
  credential_id: number;
  instance_type: string;
  preset?: string; // Tambahkan preset sebagai field opsional
  resources: {
    cpu: number;
    memory: number;
    storage: number;
  };
  network: {
    public_ip: boolean;
  };
  gcp_options?: {
    zone?: string;
    project_id?: string;
    image_project?: string;
    image_family?: string;
    tags?: string[];
    use_spot?: boolean;
    metadata?: Record<string, string>;
    service_account?: {
      scopes?: string[];
    };
  };
}

export interface VMDeploymentResponse {
  id: string;
  name: string;
  instance_id?: string;
  provider: string;
  region: string;
  status: string;
  public_ip: string | null;
  private_ip: string | null;
  last_synced?: string;
}

export interface GCPInstanceStatus {
  id: string;
  name: string;
  zone: string;
  status: string;
  machineType: string;
  networkInterfaces: Array<{
    name: string;
    networkIP: string;
    accessConfigs: Array<{
      natIP: string;
    }>;
  }>;
  disks: Array<{
    deviceName: string;
    mode: string;
    source: string;
    type: string;
  }>;
}

export interface Credential {
  id: number;
  name: string;
  type: string;
  encrypted_data: string;
}

export interface CredentialsResponse {
  credentials: Credential[];
  total: number;
}

export interface GCPInstance {
  name: string;
  id: string;
  machineType: string;
  status: string;
  zone: string;
  networkInterfaces: Array<{
    name: string;
    networkIP: string;
    accessConfigs: Array<{
      natIP: string;
    }>;
  }>;
  disks: Array<{
    deviceName: string;
    mode: string;
    source: string;
    type: string;
  }>;
}

export interface GCPInstanceList {
  [zone: string]: GCPInstance[];
}

export interface GCPCredentials {
  gcp_project_id: string;
  gcp_service_account_json: string | {
    type: string;
    project_id: string;
    private_key_id: string;
    private_key: string;
    client_email: string;
    client_id: string;
    auth_uri: string;
    token_uri: string;
    auth_provider_x509_cert_url: string;
    client_x509_cert_url: string;
  };
}

export interface CredentialDetails {
  id: number;
  name: string;
  type: string;
  created_at: string;
  updated_at: string | null;
  gcp_credentials?: GCPCredentials;
  aws_credentials?: {
    aws_access_key_id: string;
    aws_secret_access_key: string;
    aws_region: string;
  };
}

export interface ServiceAccountKey {
  type: string;
  project_id: string;
  private_key_id: string;
  private_key: string;
  client_email: string;
  client_id: string;
  auth_uri: string;
  token_uri: string;
  auth_provider_x509_cert_url: string;
  client_x509_cert_url: string;
}

export const getGCPInstanceStatus = async (
  projectId: string,
  zone: string,
  instanceName: string,
  serviceAccountKey: string | ServiceAccountKey
): Promise<GCPInstanceStatus> => {
  try {
    const accessToken = await getGCPAccessToken(serviceAccountKey);
    
    const response = await fetch(
      `https://compute.googleapis.com/compute/v1/projects/${projectId}/zones/${zone}/instances/${instanceName}`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Accept': 'application/json'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`Failed to get instance status: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      id: data.id,
      name: data.name,
      zone: data.zone,
      status: data.status,
      machineType: data.machineType,
      networkInterfaces: data.networkInterfaces,
      disks: data.disks
    };
  } catch (error) {
    console.error('Error getting GCP instance status:', error);
    throw error;
  }
};

export const getGCPAccessToken = async (serviceAccountKey: string | ServiceAccountKey): Promise<string> => {
  try {
    console.log('Getting GCP access token with service account key');
    
    // Parse service account key jika string
    let serviceAccount: ServiceAccountKey;
    if (typeof serviceAccountKey === 'string') {
      try {
        serviceAccount = JSON.parse(serviceAccountKey);
      } catch (e) {
        console.error('Error parsing service account key:', e);
        throw new Error('Invalid service account key format');
      }
    } else {
      serviceAccount = serviceAccountKey;
    }
    
    // Verifikasi service account key memiliki semua field yang diperlukan
    const requiredFields: (keyof ServiceAccountKey)[] = [
      'type',
      'project_id',
      'private_key_id',
      'private_key',
      'client_email',
      'client_id',
      'auth_uri',
      'token_uri',
      'auth_provider_x509_cert_url',
      'client_x509_cert_url'
    ];
    
    const missingFields = requiredFields.filter(field => !serviceAccount[field]);
    if (missingFields.length > 0) {
      console.error('Service account key missing required fields:', missingFields);
      throw new Error(`Service account key missing required fields: ${missingFields.join(', ')}`);
    }
    
    console.log('Service account email:', serviceAccount.client_email);
    
    // Generate JWT untuk mendapatkan token
    const now = Math.floor(Date.now() / 1000);
    const expiry = now + 3600; // 1 jam
    
    const jwt = {
      iss: serviceAccount.client_email,
      scope: 'https://www.googleapis.com/auth/cloud-platform',
      aud: 'https://oauth2.googleapis.com/token',
      exp: expiry,
      iat: now
    };
    
    // Gunakan library atau endpoint untuk sign JWT
    // Di browser, ini bisa memerlukan server proxy untuk keamanan
    
    // Sementara ini, kita gunakan service account key langsung
    // Ini bukan praktik yang aman untuk produksi
    const response = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        assertion: typeof serviceAccountKey === 'string' ? serviceAccountKey : JSON.stringify(serviceAccountKey)
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error('OAuth error response:', errorText);
      throw new Error(`Failed to get access token: ${response.statusText}`);
    }

    const data = await response.json();
    console.log('Token response:', data);
    
    if (!data.access_token) {
      throw new Error('No access token in response');
    }
    
    return data.access_token;
  } catch (error) {
    console.error('Error getting GCP access token:', error);
    throw error;
  }
};

class TerraformService {
  // Helper function untuk mendapatkan token auth
  private _getAuthToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  // Helper function untuk memastikan service account JSON dalam format string
  private _ensureServiceAccountJsonIsString(serviceAccountJson: any): string {
    if (typeof serviceAccountJson === 'string') {
      return serviceAccountJson;
    }
    
    if (typeof serviceAccountJson === 'object') {
      return JSON.stringify(serviceAccountJson);
    }
    
    throw new Error('Invalid service account JSON format');
  }

  // Fungsi untuk deploy VM dengan Terraform
  async deployVM(data: VMDeploymentRequest): Promise<VMDeploymentResponse> {
    console.log('[deployVM] Starting VM deployment with data:', data);
    
    try {
      // Gunakan endpoint yang benar dan URL lengkap
      const endpoint = 'http://localhost:8000/api/v1/vms/vms/';
      console.log('[deployVM] Using endpoint:', endpoint);
      
      // Get auth token
      const token = this._getAuthToken();
      if (!token) {
        throw new Error('Authentication token not found');
      }
      
      // Set up headers
      const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      };
      
      // Kirim request menggunakan fetch untuk kontrol lebih
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify(data),
        credentials: 'include'
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('[deployVM] Error:', response.status, errorText);
        throw new Error(`Deployment failed: ${response.status}: ${errorText}`);
      }
      
      const responseData = await response.json();
      console.log('[deployVM] Response:', responseData);
      
      return responseData;
    } catch (error: any) {
      console.error('[deployVM] Error:', error);
      throw error;
    }
  }
  
  // Fungsi untuk mendapatkan status deployment
  async getDeploymentStatus(vmId: number): Promise<VMDeploymentResponse> {
    try {
      console.log(`Getting status for VM ID: ${vmId}`);
      
      const response = await http.get<VMDeploymentResponse>(`/api/v1/vms/vms/${vmId}`);
      
      console.log('VM status response:', response.data);
      return {
        ...response.data,
        status: this._getStatusMessage(response.data.status)
      };
    } catch (error) {
      console.error('Error getting deployment status:', error);
      throw error;
    }
  }
  
  // Fungsi untuk mendapatkan daftar VM
  async listVMs(page: number = 1, limit: number = 10): Promise<{vms: VMDeploymentResponse[], total: number}> {
    try {
      const response = await http.get<{vms: VMDeploymentResponse[], total: number}>(
        `/api/v1/vms/vms/?offset=${(page-1)*limit}&limit=${limit}`
      );
      
      console.log('VM list response:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error listing VMs:', error);
      throw error;
    }
  }
  
  // Fungsi untuk menghapus VM
  async deleteVM(vmId: number): Promise<void> {
    try {
      await http.delete(`/api/v1/vms/vms/${vmId}`);
      console.log(`VM ${vmId} deleted successfully`);
    } catch (error) {
      console.error(`Error deleting VM ${vmId}:`, error);
      throw error;
    }
  }
  
  // Fungsi untuk memulai VM
  async startVM(vmId: number): Promise<VMDeploymentResponse> {
    try {
      const response = await http.post<VMDeploymentResponse>(`/api/v1/vms/vms/${vmId}/start`);
      console.log(`VM ${vmId} started:`, response.data);
      return response.data;
    } catch (error) {
      console.error(`Error starting VM ${vmId}:`, error);
      throw error;
    }
  }
  
  // Fungsi untuk stop VM
  async stopVM(vmId: number): Promise<VMDeploymentResponse> {
    try {
      const response = await http.post<VMDeploymentResponse>(`/api/v1/vms/vms/${vmId}/stop`);
      console.log(`VM ${vmId} stopped:`, response.data);
      return response.data;
    } catch (error) {
      console.error(`Error stopping VM ${vmId}:`, error);
      throw error;
    }
  }
  
  // Helper untuk mendapatkan instance type berdasarkan data deployment
  _getInstanceType(data: VMDeploymentRequest): string {
    // Jika instance_type sudah ada, gunakan itu
    if (data.instance_type) {
      return data.instance_type;
    }
    
    // Jika tidak, buat instance type berdasarkan provider
    switch (data.provider.toLowerCase()) {
      case 'aws':
        return 't2.micro'; // AWS default
      case 'gcp':
        return 'e2-small'; // GCP default
      case 'azure':
        return 'Standard_B1s'; // Azure default
      default:
        return 'small'; // Fallback generic
    }
  }
  
  // Fungsi helper untuk pesan status
  private _getStatusMessage(status: string): string {
    switch (status) {
      case 'PENDING':
        return 'Menunggu deployment';
      case 'CREATING':
        return 'Sedang membuat VM';
      case 'RUNNING':
        return 'VM berjalan';
      case 'STOPPED':
        return 'VM berhenti';
      case 'ERROR':
        return 'Error pada VM';
      case 'DELETING':
        return 'Menghapus VM';
      case 'DELETED':
        return 'VM telah dihapus';
      default:
        return status;
    }
  }

  async getVMStatus(vmId: string): Promise<VMDeploymentResponse> {
    try {
      console.log(`[getVMStatus] Getting status for VM ID: ${vmId}`);
      
      // Periksa URL endpoint relatif
      const endpoint = `/api/v1/vms/vms/${vmId}`;
      console.log(`[getVMStatus] Using endpoint: ${endpoint}`);
      
      const response = await http.get<VMDeploymentResponse>(endpoint);
      
      console.log('[getVMStatus] Response:', response.data);
      
      // Jika endpoint /api/v1/vms/vms/{vmId} tidak ada, coba /api/v1/vms/vms/{vmId}/status
      if (!response.data || !response.data.status) {
        console.warn('[getVMStatus] Invalid or empty response, trying alternate endpoint');
        
        const alternateEndpoint = `/api/v1/vms/vms/${vmId}/status`;
        console.log(`[getVMStatus] Using alternate endpoint: ${alternateEndpoint}`);
        
        const alternateResponse = await http.get<VMDeploymentResponse>(alternateEndpoint);
        console.log('[getVMStatus] Alternate response:', alternateResponse.data);
        
        return alternateResponse.data;
      }
      
      return response.data;
    } catch (error: any) {
      console.error('[getVMStatus] Error getting VM status:', error);
      
      if (error.response) {
        console.error('[getVMStatus] Error response:', error.response.status, error.response.data);
        
        // Jika error 404, coba endpoint alternatif
        if (error.response.status === 404) {
          try {
            console.log('[getVMStatus] Trying alternate endpoint after 404');
            const alternateEndpoint = `/api/v1/vms/vms/${vmId}/status`;
            const alternateResponse = await http.get<VMDeploymentResponse>(alternateEndpoint);
            return alternateResponse.data;
          } catch (altError: any) {
            console.error('[getVMStatus] Alternate endpoint also failed:', altError);
          }
        }
      }
      
      throw error;
    }
  }

  async pollVMStatus(
    vmId: string,
    onStatusChange: (status: string) => void,
    interval: number = 5000,
    maxAttempts: number = 60
  ): Promise<VMDeploymentResponse> {
    let attempts = 0;
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 3;
    
    console.log(`[pollVMStatus] Starting to poll VM status for ID: ${vmId}`);
    console.log(`[pollVMStatus] Polling interval: ${interval}ms, max attempts: ${maxAttempts}`);
    
    const poll = async (): Promise<VMDeploymentResponse> => {
      try {
        if (attempts >= maxAttempts) {
          console.warn(`[pollVMStatus] Reached max attempts (${maxAttempts}), stopping polling`);
          throw new Error('Timeout waiting for VM status');
        }
        
        attempts++;
        console.log(`[pollVMStatus] Attempt ${attempts}/${maxAttempts}`);
        
        let status: VMDeploymentResponse;
        try {
          status = await this.getVMStatus(vmId);
          // Reset consecutive errors counter on success
          consecutiveErrors = 0;
        } catch (error) {
          consecutiveErrors++;
          console.error(`[pollVMStatus] Error on attempt ${attempts}, consecutive errors: ${consecutiveErrors}`);
          
          if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            console.error(`[pollVMStatus] Too many consecutive errors (${consecutiveErrors}), stopping polling`);
            throw error;
          }
          
          // Jika error, tunggu dan coba lagi
          console.log(`[pollVMStatus] Waiting ${interval}ms before retry...`);
          await new Promise(resolve => setTimeout(resolve, interval));
          return poll();
        }
        
        // Periksa apakah status ada
        if (!status || !status.status) {
          console.warn(`[pollVMStatus] Invalid status response:`, status);
          
          if (++consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
            throw new Error('Invalid status response');
          }
          
          // Tunggu dan coba lagi
          await new Promise(resolve => setTimeout(resolve, interval));
          return poll();
        }
        
        // Beri tahu status baru
        console.log(`[pollVMStatus] Current status: ${status.status}`);
        onStatusChange(status.status);
        
        // Cek apakah sudah selesai polling
        const finalStatuses = ['RUNNING', 'FAILED', 'ERROR', 'STOPPED'];
        const normalizedStatus = status.status.toUpperCase();
        
        if (finalStatuses.includes(normalizedStatus)) {
          console.log(`[pollVMStatus] Final status reached: ${status.status}`);
          return status;
        }
        
        // Jika belum selesai, tunggu dan polling lagi
        console.log(`[pollVMStatus] Status ${status.status} is not final, waiting ${interval}ms...`);
        await new Promise(resolve => setTimeout(resolve, interval));
        return poll();
      } catch (error: any) {
        console.error('[pollVMStatus] Error during polling:', error);
        throw error;
      }
    };
    
    return poll();
  }

  async getCredentials(): Promise<CredentialsResponse> {
    const response = await http.get<CredentialsResponse>(`/api/v1/credentials/credentials/`);
    return response.data;
  }

  async decryptCredentials(encryptedData: string): Promise<string> {
    const response = await http.post(`/api/v1/credentials/credentials/${encryptedData}/details`, {
      encrypted_data: encryptedData
    });
    return response.data.decrypted_data;
  }

  async getCredentialDetails(credentialId: number): Promise<CredentialDetails> {
    try {
      const response = await axios.get(`http://localhost:8000/api/v1/credentials/credentials/${credentialId}/details`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error getting credential details:', error);
      throw error;
    }
  }

  async listGCPInstances(projectId: string, serviceAccountKey: string | ServiceAccountKey): Promise<GCPInstanceList> {
    try {
      console.log('Getting GCP instances for project:', projectId);
      
      const accessToken = await getGCPAccessToken(serviceAccountKey);
      console.log('Successfully obtained access token');
      
      // Dapatkan daftar zone yang tersedia
      const zonesResponse = await fetch(
        `https://compute.googleapis.com/compute/v1/projects/${projectId}/zones`,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Accept': 'application/json'
          }
        }
      );

      if (!zonesResponse.ok) {
        const errorText = await zonesResponse.text();
        console.error('Error getting zones:', errorText);
        throw new Error(`Failed to get zones: ${zonesResponse.statusText}`);
      }

      const zonesData = await zonesResponse.json();
      console.log(`Found ${zonesData.items?.length || 0} zones`);
      
      const instances: GCPInstanceList = {};

      // Untuk setiap zone, dapatkan daftar instance
      for (const zone of zonesData.items || []) {
        const zoneName = zone.name;
        console.log(`Fetching instances for zone: ${zoneName}`);
        
        const instancesResponse = await fetch(
          `https://compute.googleapis.com/compute/v1/projects/${projectId}/zones/${zoneName}/instances`,
          {
            headers: {
              'Authorization': `Bearer ${accessToken}`,
              'Accept': 'application/json'
            }
          }
        );

        if (instancesResponse.ok) {
          const instancesData = await instancesResponse.json();
          if (instancesData.items) {
            console.log(`Found ${instancesData.items.length} instances in zone ${zoneName}`);
            instances[zoneName] = instancesData.items.map((instance: any) => ({
              name: instance.name,
              id: instance.id,
              machineType: instance.machineType,
              status: instance.status,
              zone: zoneName,
              networkInterfaces: instance.networkInterfaces || [],
              disks: instance.disks || []
            }));
          } else {
            console.log(`No instances found in zone ${zoneName}`);
          }
        } else {
          const errorText = await instancesResponse.text();
          console.error(`Error getting instances for zone ${zoneName}:`, errorText);
        }
      }

      return instances;
    } catch (error) {
      console.error('Error listing GCP instances:', error);
      throw error;
    }
  }

  async syncVMsWithGCP(): Promise<void> {
    try {
      // Dapatkan credentials GCP
      const response = await this.getCredentials();
      console.log('Credentials response:', response);
      
      const gcpCredential = response.credentials.find((c: Credential) => c.type.toLowerCase() === 'gcp');
      console.log('Found GCP credential:', gcpCredential);
      
      if (!gcpCredential) {
        console.error('GCP credential not found');
        return;
      }

      // Dapatkan detail credential
      const credentialDetails = await this.getCredentialDetails(gcpCredential.id);
      console.log('Credential details struktur:', Object.keys(credentialDetails));
      
      // Pastikan gcp_credentials ada dan memiliki format yang benar
      if (!credentialDetails.gcp_credentials || 
          !credentialDetails.gcp_credentials.gcp_service_account_json ||
          !credentialDetails.gcp_credentials.gcp_project_id) {
        console.error('Invalid GCP credentials format:', {
          hasGcpCredentials: !!credentialDetails.gcp_credentials,
          hasServiceAccountJson: !!credentialDetails.gcp_credentials?.gcp_service_account_json,
          hasProjectId: !!credentialDetails.gcp_credentials?.gcp_project_id
        });
        return;
      }
      
      const serviceAccountKey = credentialDetails.gcp_credentials.gcp_service_account_json;
      const projectId = credentialDetails.gcp_credentials.gcp_project_id;
      
      console.log('Starting to fetch GCP instances for project:', projectId);

      // Dapatkan daftar instance dari GCP
      const gcpInstances = await this.listGCPInstances(
        projectId,
        typeof serviceAccountKey === 'string' ? serviceAccountKey : JSON.stringify(serviceAccountKey)
      );

      console.log('GCP instances fetched:', gcpInstances);

      // Dapatkan daftar VM dari database
      const dbVMs = await this.listVMs();
      console.log('DB VMs fetched:', dbVMs);

      // Update status VM berdasarkan data dari GCP
      for (const zone in gcpInstances) {
        for (const instance of gcpInstances[zone]) {
          const matchingVM = dbVMs.vms.find(vm => 
            vm.name === instance.name && 
            vm.provider.toLowerCase() === 'gcp'
          );

          if (matchingVM) {
            console.log('Found matching VM:', matchingVM.name, 'Current status:', matchingVM.status, 'GCP status:', instance.status);
            
            // Pemetaan status GCP ke status aplikasi
            const statusMapping: { [key: string]: string } = {
              'running': 'running',
              'terminated': 'stopped',
              'stopping': 'stopped',
              'starting': 'creating',
              'provisioning': 'creating',
              'staging': 'creating',
              'suspended': 'stopped'
            };

            const normalizedStatus = instance.status.toLowerCase();
            const mappedStatus = statusMapping[normalizedStatus] || 'failed';
            
            // Update VM status jika berbeda
            if (matchingVM.status.toLowerCase() !== mappedStatus) {
              console.log('[syncVMsWithGCP] Status needs update:', {
                vm: matchingVM.name,
                currentStatus: matchingVM.status,
                newStatus: mappedStatus
              });
              
              const publicIp = instance.networkInterfaces[0]?.accessConfigs[0]?.natIP;
              const privateIp = instance.networkInterfaces[0]?.networkIP;
              
              const updateData = {
                status: mappedStatus,
                public_ip: publicIp || null,
                private_ip: privateIp || null
              };
              
              console.log('[syncVMsWithGCP] Update data prepared:', updateData);
              
              try {
                console.log(`[syncVMsWithGCP] Calling updateVMStatus for VM ${matchingVM.id}`);
                await this.updateVMStatus(matchingVM.id, updateData);
                console.log(`[syncVMsWithGCP] Successfully updated VM ${matchingVM.name} status to ${mappedStatus}`);
              } catch (updateError) {
                console.error(`[syncVMsWithGCP] Failed to update VM ${matchingVM.name} status:`, updateError);
                // Lanjutkan eksekusi meskipun ada error pada satu VM
              }
            } else {
              console.log(`[syncVMsWithGCP] VM ${matchingVM.name} status already up-to-date: ${matchingVM.status}`);
            }
          } else {
            console.log('No matching VM found in database for GCP instance:', instance.name);
          }
        }
      }
    } catch (error) {
      console.error('Error syncing VMs with GCP:', error);
      throw error;
    }
  }

  async getGCPInstanceStatusViaBackend(
    credentialId: number,
    projectId: string,
    zone: string,
    instanceName: string
  ): Promise<GCPInstanceStatus> {
    try {
      console.log(`[getGCPInstanceStatusViaBackend] Getting status for ${instanceName} in ${zone}`);
      console.log(`[getGCPInstanceStatusViaBackend] Using credential ID ${credentialId}, project ${projectId}`);
      
      const requestData = {
        credential_id: credentialId,
        project_id: projectId,
        zone: zone,
        instance_name: instanceName
      };
      
      console.log('[getGCPInstanceStatusViaBackend] Request data:', requestData);
      
      // Gunakan endpoint relatif
      const endpoint = `/api/v1/vms/vms/gcp-instance-status`;
      console.log(`[getGCPInstanceStatusViaBackend] Using endpoint: ${endpoint}`);
      
      const response = await http.post(endpoint, requestData);
      
      console.log('[getGCPInstanceStatusViaBackend] Response status:', response.status);
      console.log('[getGCPInstanceStatusViaBackend] Response data:', response.data);
      
      // Cek apakah respons memiliki data yang dibutuhkan
      if (!response.data || !response.data.id || !response.data.name) {
        console.error('[getGCPInstanceStatusViaBackend] Invalid response format:', response.data);
        throw new Error('Format respons tidak valid dari backend');
      }
      
      // Map response data ke GCPInstanceStatus
      const result: GCPInstanceStatus = {
        id: response.data.id,
        name: response.data.name,
        zone: response.data.zone,
        status: response.data.status,
        machineType: response.data.machine_type,
        networkInterfaces: response.data.network_interfaces || [],
        disks: response.data.disks || []
      };
      
      console.log('[getGCPInstanceStatusViaBackend] Mapped result:', result);
      return result;
    } catch (error: any) {
      console.error('[getGCPInstanceStatusViaBackend] Error:', error);
      if (error.response) {
        console.error(
          '[getGCPInstanceStatusViaBackend] Server error:',
          error.response.status,
          error.response.data
        );
      } else if (error.request) {
        console.error('[getGCPInstanceStatusViaBackend] No response from server');
        
        // Coba fallback dengan URL lengkap
        try {
          console.log('[getGCPInstanceStatusViaBackend] Attempting fallback with absolute URL');
          const fallbackEndpoint = `${API_BASE_URL}/api/v1/vms/vms/gcp-instance-status`;
          console.log(`[getGCPInstanceStatusViaBackend] Fallback endpoint: ${fallbackEndpoint}`);
          
          const fallbackResponse = await http.post(fallbackEndpoint, {
            credential_id: credentialId,
            project_id: projectId,
            zone: zone,
            instance_name: instanceName
          });
          
          console.log('[getGCPInstanceStatusViaBackend] Fallback response:', fallbackResponse.data);
          
          // Map response data ke GCPInstanceStatus
          return {
            id: fallbackResponse.data.id,
            name: fallbackResponse.data.name,
            zone: fallbackResponse.data.zone,
            status: fallbackResponse.data.status,
            machineType: fallbackResponse.data.machine_type,
            networkInterfaces: fallbackResponse.data.network_interfaces || [],
            disks: fallbackResponse.data.disks || []
          };
        } catch (fallbackError) {
          console.error('[getGCPInstanceStatusViaBackend] Fallback also failed:', fallbackError);
        }
      } else {
        console.error('[getGCPInstanceStatusViaBackend] Request setup error:', error.message);
      }
      throw error;
    }
  }

  async updateVMStatus(vmId: string, updateData: {
    status: string;
    public_ip: string | null;
    private_ip: string | null;
  }): Promise<void> {
    try {
      console.log(`[updateVMStatus] Updating VM ${vmId} with data:`, updateData);
      
      // Buat kopi objek untuk memastikan format data yang benar
      const dataToSend = {
        status: updateData.status,
        public_ip: updateData.public_ip,
        private_ip: updateData.private_ip
      };
      
      console.log('[updateVMStatus] Sending data:', dataToSend);
      console.log(`[updateVMStatus] Using endpoint: ${API_BASE_URL}/api/v1/vms/vms/${vmId}`);
      
      // Coba tanpa menggunakan API_BASE_URL yang mungkin tidak terdefinisi dengan benar
      const endpoint = `/api/v1/vms/vms/${vmId}`;
      console.log(`[updateVMStatus] Simplified endpoint: ${endpoint}`);
      
      const response = await http.put(endpoint, dataToSend);
      
      console.log('[updateVMStatus] Success response:', response.data);
      return response.data;
    } catch (error: any) {
      console.error('[updateVMStatus] Error updating VM status:', error);
      if (error.response) {
        console.error('[updateVMStatus] Error response:', error.response.status, error.response.data);
      } else if (error.request) {
        console.error('[updateVMStatus] No response received from server');
      } else {
        console.error('[updateVMStatus] Error setting up request:', error.message);
      }
      
      // Coba fallback dengan URL lengkap jika endpoint relatif gagal
      if (error.request && !error.response) {
        try {
          console.log('[updateVMStatus] Attempting fallback with absolute URL');
          const fallbackEndpoint = `${API_BASE_URL}/api/v1/vms/vms/${vmId}`;
          console.log(`[updateVMStatus] Fallback endpoint: ${fallbackEndpoint}`);
          
          const fallbackResponse = await http.put(fallbackEndpoint, {
            status: updateData.status,
            public_ip: updateData.public_ip,
            private_ip: updateData.private_ip
          });
          
          console.log('[updateVMStatus] Fallback response:', fallbackResponse.data);
          return fallbackResponse.data;
        } catch (fallbackError) {
          console.error('[updateVMStatus] Fallback also failed:', fallbackError);
          throw fallbackError;
        }
      }
      
      throw error;
    }
  }

  async uploadGCPJson(formData: FormData): Promise<any> {
    const response = await http.post<any>(`${API_BASE_URL}/api/v1/credentials/upload-gcp-json`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  }

  async createCredential(data: {
    name: string;
    type: string;
    gcp_credentials?: {
      gcp_project_id: string;
      gcp_service_account_json: {
        type: string;
        project_id: string;
        private_key_id: string;
        private_key: string;
        client_email: string;
        client_id: string;
        auth_uri?: string;
        token_uri?: string;
        auth_provider_x509_cert_url?: string;
        client_x509_cert_url?: string;
      }
    }
  }): Promise<any> {
    const response = await http.post<any>(`${API_BASE_URL}/api/v1/credentials/credentials/`, data);
    return response.data;
  }

  // Fungsi untuk mendapatkan credential details dengan memastikan format yang benar
  async _getCredentialDetailsWithProperFormat(credentialId: number): Promise<any> {
    try {
      console.log(`[_getCredentialDetailsWithProperFormat] Getting details for credential ID: ${credentialId}`);
      
      const response = await http.get<CredentialDetails>(`${API_BASE_URL}/api/v1/credentials/credentials/${credentialId}/details`);
      const credentialDetails = response.data;
      
      // Jika ada kredensial GCP, pastikan service_account_json dalam format string
      if (credentialDetails.gcp_credentials && credentialDetails.gcp_credentials.gcp_service_account_json) {
        if (typeof credentialDetails.gcp_credentials.gcp_service_account_json === 'object') {
          console.log('[_getCredentialDetailsWithProperFormat] Converting gcp_service_account_json from object to string');
          credentialDetails.gcp_credentials.gcp_service_account_json = 
            JSON.stringify(credentialDetails.gcp_credentials.gcp_service_account_json);
        }
      }
      
      return credentialDetails;
    } catch (error) {
      console.error('[_getCredentialDetailsWithProperFormat] Error getting credential details:', error);
      throw error;
    }
  }

  // Helper method untuk mengatasi masalah decrypting credential
  async simplifiedDeployVM(data: any): Promise<any> {
    console.log('[simplifiedDeployVM] Memulai deployment VM sederhana dengan data:', data);
    
    try {
      // 1. Pastikan credential_id adalah angka
      const credentialId = typeof data.credential_id === 'string' 
        ? parseInt(data.credential_id, 10) 
        : data.credential_id;
      
      console.log('[simplifiedDeployVM] Credential ID:', credentialId);
      
      // 2. Persiapkan data SANGAT SEDERHANA sesuai dengan format API
      // HAPUS SEMUA field kompleks untuk menghindari masalah serialisasi/deserialisasi
      const deploymentData = {
        name: data.name,
        provider: data.provider.toLowerCase(),
        region: data.region,
        credential_id: credentialId,
        instance_type: data.instance_type || 'e2-micro',
        resources: {
          cpu: data.resources?.cpu || 2,
          memory: data.resources?.memory || 4,
          storage: data.resources?.storage || 10
        },
        network: {
          public_ip: true
        }
      };
      
      // JANGAN sertakan gcp_options sama sekali!
      
      console.log('[simplifiedDeployVM] Data deployment yang disederhanakan:', JSON.stringify(deploymentData));
      
      // 3. Gunakan fetch API untuk kontrol lebih baik
      const endpoint = 'http://localhost:8000/api/v1/vms/vms/';
      console.log(`[simplifiedDeployVM] Menggunakan endpoint: ${endpoint}`);
      
      // JSON stringify untuk memastikan format benar
      const serializedData = JSON.stringify(deploymentData);
      
      // 4. Set headers dengan token auth
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      };
      
      // Tambahkan token auth jika tersedia
      const token = localStorage.getItem('auth_token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      console.log('[simplifiedDeployVM] Headers:', headers);
      
      // 5. Kirim request dengan fetch
      console.log('[simplifiedDeployVM] Mengirim request...');
      // Gunakan URL langsung
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: headers,
        body: serializedData,
        credentials: 'include'
      });
      
      // 6. Periksa response
      if (!response.ok) {
        const errorText = await response.text();
        console.error('[simplifiedDeployVM] Error response:', response.status, errorText);
        throw new Error(`Deployment gagal (${response.status}): ${errorText}`);
      }
      
      const responseData = await response.json();
      console.log('[simplifiedDeployVM] VM deployment response:', responseData);
      
      return responseData;
    } catch (error: any) {
      console.error('[simplifiedDeployVM] Error:', error);
      
      if (error.response) {
        console.error('[simplifiedDeployVM] Response error:', error.response.data);
        throw new Error(`Deployment gagal: ${JSON.stringify(error.response.data)}`);
      } else if (error.request) {
        throw new Error('Tidak ada respons dari server');
      } else {
        throw new Error(error.message || 'Terjadi kesalahan saat mengirim permintaan');
      }
    }
  }

  async simplifiedGetGCPStatus(credentialId: number, projectId: string, zone: string, instanceName: string): Promise<any> {
    console.log('simplifiedGetGCPStatus - Memulai proses dengan:', {
      credentialId,
      projectId, 
      zone,
      instanceName
    });
    
    try {
      // 1. Verifikasi parameter
      console.log('simplifiedGetGCPStatus - Memeriksa parameter...');
      if (!credentialId) throw new Error('Credential ID diperlukan');
      if (!projectId) throw new Error('Project ID diperlukan');
      if (!zone) throw new Error('Zone diperlukan');
      if (!instanceName) throw new Error('Instance name diperlukan');
      
      // 2. Dapatkan token
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        throw new Error('Token autentikasi tidak ditemukan');
      }
      
      // 3. Siapkan data request
      console.log('simplifiedGetGCPStatus - Menyiapkan data request...');
      const data = {
        credential_id: credentialId,
        project_id: projectId,
        zone: zone,
        instance_name: instanceName
      };
      
      // 4. Set headers and config
      console.log('simplifiedGetGCPStatus - Setting up request config...');
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      
      const config = {
        headers,
        timeout: 30000 // 30 seconds timeout
      };
      
      // 5. Kirim request
      console.log('simplifiedGetGCPStatus - Mengirim request ke /vm/gcp-instance-status...');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/vm/gcp-instance-status`,
        data,
        config
      );
      
      // 6. Periksa respons
      console.log('simplifiedGetGCPStatus - Respons diterima:', response.status);
      console.log('simplifiedGetGCPStatus - Data respons:', response.data);
      
      return response.data;
    } catch (error: any) {
      // Error handling spesifik
      console.error('simplifiedGetGCPStatus - Error terjadi:');
      
      if (error.response) {
        // Respons diterima tapi dengan status error
        console.error('simplifiedGetGCPStatus - Response error:', {
          status: error.response.status,
          data: error.response.data
        });
        throw new Error(`Response error (${error.response.status}): ${JSON.stringify(error.response.data)}`);
      } else if (error.request) {
        // Request dibuat tapi tidak ada respons
        console.error('simplifiedGetGCPStatus - Request timeout atau network error:', error.request);
        throw new Error('Tidak ada respons dari server setelah 30 detik');
      } else {
        // Error pada setup request
        console.error('simplifiedGetGCPStatus - Setup error:', error.message);
        throw new Error(`Setup error: ${error.message}`);
      }
    }
  }

  async simplifiedSyncWithGCP(credentialId: number, projectId: string, zone: string): Promise<any> {
    console.log('simplifiedSyncWithGCP - Memulai proses sinkronisasi dengan GCP');
    console.log('Parameter:', { credentialId, projectId, zone });
    
    try {
      // 1. Verifikasi parameter
      if (!credentialId) throw new Error('Credential ID diperlukan');
      if (!projectId) throw new Error('Project ID diperlukan');
      if (!zone) throw new Error('Zone diperlukan');
      
      // 2. Dapatkan token
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        throw new Error('Token autentikasi tidak ditemukan');
      }
      
      // 3. Siapkan data request
      const data = {
        credential_id: credentialId,
        project_id: projectId,
        zone: zone
      };
      
      // 4. Set headers dan config
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      
      const config = {
        headers,
        timeout: 60000 // 60 detik timeout untuk operasi yang lebih lama
      };
      
      // 5. Kirim request ke endpoint sync
      console.log('simplifiedSyncWithGCP - Mengirim request ke /vm/sync-gcp-vms');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/vm/sync-gcp-vms`,
        data,
        config
      );
      
      // 6. Log dan return hasil
      console.log('simplifiedSyncWithGCP - Response diterima:', response.status);
      console.log('simplifiedSyncWithGCP - Data:', response.data);
      
      return response.data;
    } catch (error: any) {
      console.error('simplifiedSyncWithGCP - Error terjadi:');
      
      if (error.response) {
        console.error('simplifiedSyncWithGCP - Response error:', {
          status: error.response.status,
          data: error.response.data
        });
        throw new Error(`Response error (${error.response.status}): ${JSON.stringify(error.response.data)}`);
      } else if (error.request) {
        console.error('simplifiedSyncWithGCP - Request timeout atau network error:', error.request);
        throw new Error('Tidak ada respons dari server setelah 60 detik');
      } else {
        console.error('simplifiedSyncWithGCP - Setup error:', error.message);
        throw new Error(`Setup error: ${error.message}`);
      }
    }
  }

  async debugGCPCredential(credentialId: number): Promise<any> {
    console.log('debugGCPCredential - Memulai proses debug kredensial GCP untuk ID:', credentialId);
    
    try {
      // 1. Coba dapatkan detail kredensial
      console.log('debugGCPCredential - Mendapatkan detail kredensial...');
      const credentialDetails = await this.getCredentialDetails(credentialId);
      
      // 2. Log struktur kredensial
      console.log('debugGCPCredential - Struktur kredensial:', {
        id: credentialDetails.id,
        name: credentialDetails.name,
        type: credentialDetails.type,
        hasGCPCredentials: !!credentialDetails.gcp_credentials,
        created_at: credentialDetails.created_at
      });
      
      // 3. Periksa apakah GCP credentials tersedia dan valid
      if (!credentialDetails.gcp_credentials) {
        console.error('debugGCPCredential - MASALAH: GCP credentials tidak ditemukan');
        return {
          status: 'error',
          message: 'GCP credentials tidak ditemukan',
          details: credentialDetails
        };
      }
      
      // 4. Periksa project_id dan service_account_json
      const { gcp_project_id, gcp_service_account_json } = credentialDetails.gcp_credentials;
      
      console.log('debugGCPCredential - Project ID:', gcp_project_id);
      console.log('debugGCPCredential - Service Account JSON type:', typeof gcp_service_account_json);
      
      if (!gcp_project_id) {
        console.error('debugGCPCredential - MASALAH: project_id tidak ditemukan');
        return {
          status: 'error',
          message: 'GCP project_id tidak ditemukan',
          details: credentialDetails.gcp_credentials
        };
      }
      
      if (!gcp_service_account_json) {
        console.error('debugGCPCredential - MASALAH: service_account_json tidak ditemukan');
        return {
          status: 'error',
          message: 'GCP service_account_json tidak ditemukan',
          details: credentialDetails.gcp_credentials
        };
      }
      
      // 5. Periksa apakah service_account_json dalam format yang benar
      let serviceAccountObj: any;
      try {
        if (typeof gcp_service_account_json === 'string') {
          serviceAccountObj = JSON.parse(gcp_service_account_json);
        } else {
          serviceAccountObj = gcp_service_account_json;
        }
        
        // 6. Periksa kunci yang diperlukan dalam service_account_json
        const requiredKeys = [
          'type', 'project_id', 'private_key_id', 'private_key', 
          'client_email', 'client_id', 'auth_uri', 'token_uri'
        ];
        
        const missingKeys = requiredKeys.filter(key => !serviceAccountObj[key]);
        
        if (missingKeys.length > 0) {
          console.error('debugGCPCredential - MASALAH: Kunci yang diperlukan tidak ada dalam service_account_json:', missingKeys);
          return {
            status: 'error',
            message: `Kunci yang diperlukan tidak ada dalam service_account_json: ${missingKeys.join(', ')}`,
            details: Object.keys(serviceAccountObj)
          };
        }
        
        // 7. Periksa apakah project_id di service_account_json cocok dengan project_id di atas
        if (serviceAccountObj.project_id !== gcp_project_id) {
          console.warn('debugGCPCredential - PERINGATAN: project_id di service_account_json tidak cocok dengan project_id di kredensial');
          console.warn(`service_account project_id: ${serviceAccountObj.project_id} | credential project_id: ${gcp_project_id}`);
        }
        
        // 8. Validasi format private_key
        if (!serviceAccountObj.private_key.includes('BEGIN PRIVATE KEY') || 
            !serviceAccountObj.private_key.includes('END PRIVATE KEY')) {
          console.error('debugGCPCredential - MASALAH: Format private_key tidak valid');
          return {
            status: 'error',
            message: 'Format private_key tidak valid',
            details: { keyLength: serviceAccountObj.private_key.length }
          };
        }
        
        // Kredensial valid
        return {
          status: 'success',
          message: 'Kredensial GCP valid dan lengkap',
          projectId: gcp_project_id,
          serviceAccount: {
            type: serviceAccountObj.type,
            project_id: serviceAccountObj.project_id,
            client_email: serviceAccountObj.client_email
          }
        };
        
      } catch (parseError) {
        console.error('debugGCPCredential - MASALAH: Gagal memparse service_account_json:', parseError);
        return {
          status: 'error',
          message: 'Gagal memparse service_account_json',
          details: { 
            error: (parseError as Error).message,
            rawLength: typeof gcp_service_account_json === 'string' ? gcp_service_account_json.length : 'object'
          }
        };
      }
      
    } catch (error: any) {
      console.error('debugGCPCredential - Error saat mendebug kredensial:', error);
      
      if (error.response) {
        console.error('debugGCPCredential - Response error:', {
          status: error.response.status,
          data: error.response.data
        });
        return {
          status: 'error',
          message: `Response error (${error.response.status})`,
          details: error.response.data
        };
      }
      
      return {
        status: 'error',
        message: error.message || 'Error tidak diketahui',
        details: error
      };
    }
  }

  // Fungsi untuk memastikan service account key dalam format string dengan parameter credential ID
  private async _sanitizeServiceAccountKey(credentialId: number): Promise<{ projectId: string, serviceAccountKey: string }>;
  // Overload untuk menerima objek JSON langsung
  private async _sanitizeServiceAccountKey(serviceAccountJson: any): Promise<{ projectId: string, serviceAccountKey: string }>;
  // Implementasi
  private async _sanitizeServiceAccountKey(param: number | any): Promise<{ projectId: string, serviceAccountKey: string }> {
    try {
      let projectId: string;
      let serviceAccountKeyStr: string;
      
      // Jika param adalah number, ambil credential details berdasarkan ID
      if (typeof param === 'number') {
        console.log('[_sanitizeServiceAccountKey] Getting credential details for ID:', param);
        const credentialDetails = await this.getCredentialDetails(param);
        
        if (!credentialDetails.gcp_credentials) {
          throw new Error('Kredensial GCP tidak ditemukan');
        }
        
        const { gcp_project_id, gcp_service_account_json } = credentialDetails.gcp_credentials;
        
        if (!gcp_project_id) {
          throw new Error('Project ID tidak ditemukan di kredensial GCP');
        }
        
        if (!gcp_service_account_json) {
          throw new Error('Service account JSON tidak ditemukan di kredensial GCP');
        }
        
        projectId = gcp_project_id;
        
        // Pastikan service account key dalam format string
        if (typeof gcp_service_account_json === 'string') {
          // Verifikasi bahwa ini adalah string JSON yang valid
          try {
            const parsed = JSON.parse(gcp_service_account_json);
            serviceAccountKeyStr = gcp_service_account_json;
            console.log('[_sanitizeServiceAccountKey] Service account key sudah dalam format string dan valid');
          } catch (e) {
            console.error('[_sanitizeServiceAccountKey] Service account key bukan JSON valid:', e);
            throw new Error('Service account key bukan JSON valid');
          }
        } else if (typeof gcp_service_account_json === 'object') {
          // Konversi objek ke string
          serviceAccountKeyStr = JSON.stringify(gcp_service_account_json);
          console.log('[_sanitizeServiceAccountKey] Service account key dikonversi dari objek ke string');
        } else {
          throw new Error(`Service account key dalam format tidak didukung: ${typeof gcp_service_account_json}`);
        }
      } 
      // Jika param adalah objek JSON langsung
      else if (typeof param === 'object') {
        console.log('[_sanitizeServiceAccountKey] Processing direct service account JSON object');
        
        if (param.project_id) {
          projectId = param.project_id;
        } else {
          throw new Error('Project ID tidak ditemukan dalam service account JSON');
        }
        
        serviceAccountKeyStr = JSON.stringify(param);
        console.log('[_sanitizeServiceAccountKey] Direct service account JSON converted to string');
      }
      // Jika param adalah string JSON
      else if (typeof param === 'string') {
        console.log('[_sanitizeServiceAccountKey] Processing service account JSON string');
        serviceAccountKeyStr = param;
        
        try {
          const parsed = JSON.parse(param);
          if (parsed.project_id) {
            projectId = parsed.project_id;
          } else {
            throw new Error('Project ID tidak ditemukan dalam service account JSON');
          }
        } catch (e) {
          console.error('[_sanitizeServiceAccountKey] Invalid JSON string:', e);
          throw new Error('Format service account key tidak valid');
        }
      }
      else {
        throw new Error(`Parameter tidak didukung: ${typeof param}`);
      }
      
      return {
        projectId,
        serviceAccountKey: serviceAccountKeyStr
      };
    } catch (error: any) {
      console.error('[_sanitizeServiceAccountKey] Error:', error);
      throw error;
    }
  }

  // Fungsi untuk melakukan test deployment langsung ke Google Cloud API
  async testDirectGCPDeployment(credentialId: number, vmName: string, zone: string = "us-central1-a"): Promise<any> {
    console.log('[testDirectGCPDeployment] Starting direct GCP deployment test');
    
    try {
      // 1. Sanitize kredensial
      const { projectId, serviceAccountKey } = await this._sanitizeServiceAccountKey(credentialId);
      console.log('[testDirectGCPDeployment] Got sanitized credentials for project:', projectId);
      
      // 2. Parse service account key untuk mendapatkan akses token
      let serviceAccount: any;
      try {
        serviceAccount = JSON.parse(serviceAccountKey);
        console.log('[testDirectGCPDeployment] Parsed service account key successfully');
      } catch (e) {
        console.error('[testDirectGCPDeployment] Failed to parse service account key:', e);
        throw new Error('Failed to parse service account key');
      }
      
      // 3. Buat VM minimal langsung ke GCP API
      console.log('[testDirectGCPDeployment] Creating minimal VM with name:', vmName, 'in zone:', zone);
      
      // Informasi lebih detail akan diimplementasikan jika diperlukan
      return {
        status: 'prepared',
        message: 'Kredensial disiapkan dengan benar untuk deployment langsung',
        projectId,
        vmName,
        zone
      };
    } catch (error: any) {
      console.error('[testDirectGCPDeployment] Error:', error);
      return {
        status: 'error',
        message: error.message || 'Error tidak diketahui',
        error
      };
    }
  }

  async debugDeployVM(credentialId: number, vmName: string, zone: string = "us-central1-a"): Promise<any> {
    console.log('debugDeployVM - Memulai proses debug deploy VM dengan:');
    console.log({credentialId, vmName, zone});
    
    try {
      // 1. Periksa kredensial terlebih dahulu
      console.log('debugDeployVM - Memeriksa kredensial...');
      const credentialCheck = await this.debugGCPCredential(credentialId);
      
      if (credentialCheck.status !== 'success') {
        console.error('debugDeployVM - Kredensial tidak valid:', credentialCheck);
        return {
          status: 'error',
          step: 'credential_check',
          message: 'Kredensial tidak valid',
          details: credentialCheck
        };
      }
      
      // 2. Ambil kredensial yang sudah disanitasi (pastikan dalam format string)
      try {
        const { projectId, serviceAccountKey } = await this._sanitizeServiceAccountKey(credentialId);
        console.log('debugDeployVM - Kredensial disanitasi dengan sukses untuk project:', projectId);
      } catch (sanitizeError) {
        console.error('debugDeployVM - Error saat sanitasi kredensial:', sanitizeError);
        return {
          status: 'error',
          step: 'credential_sanitize',
          message: 'Error saat menyiapkan kredensial: ' + (sanitizeError as Error).message,
          error: sanitizeError
        };
      }
      
      // 3. Siapkan data minimal untuk deployment
      const region = zone.split('-').slice(0, 2).join('-'); // Ekstrak region dari zone, mis: us-central1-a -> us-central1
      const deployData: VMDeploymentRequest = {
        name: vmName,
        provider: 'gcp',
        region: region,
        zone: zone,
        credential_id: credentialId,
        instance_type: 'e2-small', // Gunakan tipe instance default
        resources: {
          cpu: 2,
          memory: 4,
          storage: 20
        },
        network: {
          public_ip: true
        },
        // Hanya gunakan field minimal yang diperlukan dalam gcp_options
        gcp_options: {
          zone
        }
      };
      
      console.log('debugDeployVM - Data deployment:', deployData);
      
      // 4. Coba deploy VM menggunakan simplified method
      console.log('debugDeployVM - Melakukan deployment VM...');
      try {
        const deployResult = await this.simplifiedDeployVM(deployData);
        console.log('debugDeployVM - Deployment berhasil:', deployResult);
        
        return {
          status: 'success',
          step: 'deployment',
          message: 'VM berhasil di-deploy',
          vm: deployResult
        };
      } catch (deployError: any) {
        console.error('debugDeployVM - Error saat deployment:', deployError);
        
        return {
          status: 'error',
          step: 'deployment',
          message: deployError.message || 'Gagal melakukan deployment VM',
          error: deployError
        };
      }
    } catch (error: any) {
      console.error('debugDeployVM - Error tidak terduga:', error);
      
      return {
        status: 'error',
        step: 'unknown',
        message: error.message || 'Error tidak terduga',
        error
      };
    }
  }

  async createGCPVM(credentialId: string | number, vmConfig: {
    name: string;
    region?: string;
    zone?: string;
    machineType?: string;
    diskSizeGB?: number;
    tags?: string[];
    useSpot?: boolean;
  }): Promise<{ success: boolean; message: string; vm?: any; terraformPreview?: string }> {
    try {
      console.log(`[createGCPVM] Memulai pembuatan VM dengan credential ID: ${credentialId}`, vmConfig);
      
      // Konversi credentialId ke number jika perlu
      const numericCredentialId = typeof credentialId === 'string' ? 
        parseInt(credentialId, 10) : credentialId;
        
      // Debug GCP credential
      const credentialCheck = await this.debugGCPCredential(numericCredentialId);
      if (credentialCheck.status !== 'success') {
        console.error('[createGCPVM] Kredensial tidak valid:', credentialCheck);
        throw new Error(`Kredensial tidak valid: ${credentialCheck.message}`);
      }
      
      // Ambil project ID dari hasil debug credential
      const projectId = credentialCheck.projectId;
      console.log(`[createGCPVM] Menggunakan project ID: ${projectId}`);
      
      // Pastikan service account dalam format string yang valid
      try {
        const { serviceAccountKey } = await this._sanitizeServiceAccountKey(numericCredentialId);
        console.log('[createGCPVM] Service account berhasil disanitasi');
      } catch (error) {
        console.error('[createGCPVM] Error saat sanitasi service account:', error);
        // Tetap lanjutkan proses
      }
      
      // Persiapkan parameter untuk VM
      const region = vmConfig.region || 'us-central1';
      const zone = vmConfig.zone || `${region}-a`;
      const machineType = vmConfig.machineType || 'e2-micro';
      const diskSizeGB = vmConfig.diskSizeGB || 10;
      const tags = vmConfig.tags || ['http-server', 'https-server'];
      const useSpot = vmConfig.useSpot !== undefined ? vmConfig.useSpot : true;
      
      // Generate config Terraform untuk debugging
      const terraformPreview = await this.generateTerraformConfig(
        projectId,
        {
          name: vmConfig.name,
          machineType,
          zone,
          diskSizeGB,
          useSpot,
          tags
        }
      );
      console.log(`[createGCPVM] TF Config Preview: ${terraformPreview.substring(0, 100)}...`);
      
      // Sesuaikan data ke format yang diharapkan endpoint POST /api/v1/vms/vms/
      // PERUBAHAN: Hilangkan gcp_options dari data yang dikirim ke backend
      const deployData: any = {
        name: vmConfig.name,
        provider: 'gcp', // Lowercase sesuai dengan model di backend
        region: region,
        credential_id: numericCredentialId,
        instance_type: machineType,
        resources: {
          cpu: machineType.includes('micro') ? 1 : 2,
          memory: machineType.includes('micro') ? 1 : 4,
          storage: diskSizeGB
        },
        network: {
          public_ip: true
        }
        // PENTING: Hapus gcp_options agar backend tidak kesulitan mendekripsi kredensial
      };
      
      console.log(`[createGCPVM] Data deployment yang disederhanakan: ${JSON.stringify(deployData)}`);
      
      // Kirim request ke endpoint post /api/v1/vms/vms/
      console.log('[createGCPVM] Mengirim request ke endpoint /api/v1/vms/vms/');
      
      // PERUBAHAN: Gunakan simplifiedDeployVM yang lebih sederhana alih-alih deployVM
      // untuk menghindari masalah format data
      const result = await this.simplifiedDeployVM(deployData);
      console.log(`[createGCPVM] Hasil deploy: ${JSON.stringify(result)}`);
      
      return {
        success: true,
        message: `VM ${vmConfig.name} berhasil di-deploy pada GCP project ${projectId}`,
        vm: result,
        terraformPreview
      };
    } catch (error) {
      console.error('[createGCPVM] Error:', error);
      return { 
        success: false, 
        message: `Gagal membuat VM: ${error instanceof Error ? error.message : String(error)}` 
      };
    }
  }

  async generateTerraformConfig(
    projectId: string,
    vmConfig: {
      name: string;
      machineType: string;
      zone: string;
      diskSizeGB: number;
      useSpot: boolean;
      tags: string[];
    }
  ): Promise<string> {
    // Generate Terraform configuration untuk GCP VM
    const terraformConfig = `
provider "google" {
  project     = "${projectId}"
  region      = "${vmConfig.zone.substring(0, vmConfig.zone.lastIndexOf('-'))}"
  zone        = "${vmConfig.zone}"
}

resource "google_compute_instance" "${vmConfig.name}" {
  name         = "${vmConfig.name}"
  machine_type = "${vmConfig.machineType}"
  zone         = "${vmConfig.zone}"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = ${vmConfig.diskSizeGB}
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  ${vmConfig.tags.length > 0 ? `tags = ["${vmConfig.tags.join('", "')}"]` : ''}

  ${vmConfig.useSpot ? 
  `scheduling {
    preemptible       = true
    automatic_restart = false
    provisioning_model = "SPOT"
  }` : ''}

  metadata = {
    enable-osconfig = "TRUE"
  }

  service_account {
    scopes = [
      "https://www.googleapis.com/auth/devstorage.read_only",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring.write",
      "https://www.googleapis.com/auth/service.management.readonly",
      "https://www.googleapis.com/auth/servicecontrol"
    ]
  }
}

output "instance_id" {
  value = google_compute_instance.${vmConfig.name}.id
}

output "public_ip" {
  value = google_compute_instance.${vmConfig.name}.network_interface[0].access_config[0].nat_ip
}`;

    return terraformConfig;
  }

  async checkGCPVMStatus(vmId: string, credentialId: number): Promise<any> {
    try {
      console.log(`[checkGCPVMStatus] Memeriksa status VM ${vmId} dengan credential ${credentialId}`);
      
      // 1. Dapatkan detail VM terlebih dahulu
      const vmDetails = await this.getVMStatus(vmId);
      console.log(`[checkGCPVMStatus] Detail VM:`, vmDetails);
      
      if (!vmDetails || vmDetails.provider.toLowerCase() !== 'gcp') {
        throw new Error('VM bukan tipe GCP');
      }
      
      // 2. Dapatkan detail kredensial untuk project_id dan zone
      const credentialDetails = await this.getCredentialDetails(credentialId);
      
      if (!credentialDetails.gcp_credentials) {
        throw new Error('Kredensial GCP tidak valid');
      }
      
      const projectId = credentialDetails.gcp_credentials.gcp_project_id;
      
      // Zone bisa dari VM data atau default dari region
      // VMDeploymentResponse mungkin tidak memiliki gcp_options
      // Gunakan properti apa pun yang tersedia atau gunakan default
      let zone = `${vmDetails.region}-a`; // Default zone dari region
      
      // Jika vmDetails memiliki data tambahan yang menyimpan zone, gunakan itu
      const vmDetailsAny = vmDetails as any;
      if (vmDetailsAny.gcp_options?.zone) {
        zone = vmDetailsAny.gcp_options.zone;
      } else if (vmDetailsAny.zone) {
        zone = vmDetailsAny.zone;
      }
      
      console.log(`[checkGCPVMStatus] Menggunakan project ${projectId} dan zone ${zone}`);
      
      // 3. Gunakan endpoint /api/v1/vms/vms/gcp-instance-status untuk mendapatkan status
      const requestData = {
        credential_id: credentialId,
        project_id: projectId,
        zone: zone,
        instance_name: vmDetails.name
      };
      
      console.log(`[checkGCPVMStatus] Memanggil endpoint gcp-instance-status dengan data:`, requestData);
      
      const endpoint = `/api/v1/vms/vms/gcp-instance-status`;
      const response = await http.post(endpoint, requestData);
      
      console.log(`[checkGCPVMStatus] Response:`, response.data);
      
      // 4. Proses hasil dan kembalikan informasi status
      const status = response.data.status;
      const publicIp = response.data.network_interfaces?.[0]?.accessConfigs?.[0]?.natIP;
      const privateIp = response.data.network_interfaces?.[0]?.networkIP;
      
      // 5. Jika status berbeda dari yang tercatat di DB, update status di DB
      if (status && status.toLowerCase() !== vmDetails.status.toLowerCase()) {
        console.log(`[checkGCPVMStatus] Status perlu diupdate: ${vmDetails.status} -> ${status}`);
        
        const statusMappings: Record<string, string> = {
          'running': 'running',
          'terminated': 'stopped',
          'stopping': 'stopped',
          'starting': 'creating',
          'provisioning': 'creating',
          'staging': 'creating'
        };
        
        const mappedStatus = statusMappings[status.toLowerCase()] || status;
        
        // Update status VM di DB
        await this.updateVMStatus(vmId, {
          status: mappedStatus,
          public_ip: publicIp || null,
          private_ip: privateIp || null
        });
        
        console.log(`[checkGCPVMStatus] Status berhasil diupdate ke ${mappedStatus}`);
      }
      
      return {
        success: true,
        vm: vmDetails,
        gcp_status: {
          status,
          publicIp,
          privateIp,
          zone: response.data.zone,
          machineType: response.data.machine_type
        }
      };
    } catch (error: any) {
      console.error(`[checkGCPVMStatus] Error:`, error);
      
      return {
        success: false,
        message: error.message || 'Gagal memeriksa status VM',
        error: error
      };
    }
  }

  async getVMDeploymentLogs(vmId: string): Promise<any> {
    try {
      console.log(`[getVMDeploymentLogs] Mendapatkan log deployment untuk VM ID: ${vmId}`);
      
      // Cek apakah VM ada dan dapatkan detailnya
      const vmDetails = await this.getVMStatus(vmId);
      console.log(`[getVMDeploymentLogs] Detail VM:`, {
        id: vmDetails.id,
        name: vmDetails.name,
        provider: vmDetails.provider,
        status: vmDetails.status
      });
      
      // Gunakan endpoint yang sesuai untuk mendapatkan log
      // Endpoint ini mungkin tidak ada, sehingga dibuat fallback
      let logEndpoint = `/api/v1/vms/vms/${vmId}/logs`;
      console.log(`[getVMDeploymentLogs] Mencoba endpoint logs:`, logEndpoint);
      
      try {
        const response = await http.get(logEndpoint);
        console.log(`[getVMDeploymentLogs] Log berhasil diambil`);
        return {
          success: true,
          logs: response.data,
          vm: {
            id: vmDetails.id,
            name: vmDetails.name,
            status: vmDetails.status
          }
        };
      } catch (error: any) {
        // Jika endpoint log tidak ada, gunakan simulasi log berdasarkan status VM
        console.log(`[getVMDeploymentLogs] Tidak bisa mendapatkan log, menggunakan simulasi log`);
        
        // Gunakan waktu saat ini sebagai timestamp awal jika created_at tidak tersedia
        // VMDeploymentResponse mungkin tidak memiliki created_at
        const vmDetailsAny = vmDetails as any;
        const creationTime = vmDetailsAny.created_at || vmDetailsAny.last_synced || new Date().toISOString();
        
        const simulatedLogs = [
          {
            timestamp: creationTime,
            message: `Starting deployment of VM ${vmDetails.name}`,
            level: 'INFO'
          },
          {
            timestamp: new Date().toISOString(),
            message: `Current VM status: ${vmDetails.status}`,
            level: 'INFO'
          }
        ];
        
        // Tambahkan log berdasarkan status
        if (vmDetails.status.toLowerCase() === 'running') {
          simulatedLogs.push({
            timestamp: new Date().toISOString(),
            message: `VM deployed successfully. Public IP: ${vmDetails.public_ip || 'Not assigned'}`,
            level: 'INFO'
          });
        } else if (vmDetails.status.toLowerCase() === 'error' || vmDetails.status.toLowerCase() === 'failed') {
          simulatedLogs.push({
            timestamp: new Date().toISOString(),
            message: `VM deployment failed. Check cloud provider logs for details.`,
            level: 'ERROR'
          });
        } else if (vmDetails.status.toLowerCase() === 'creating') {
          simulatedLogs.push({
            timestamp: new Date().toISOString(),
            message: `VM is being created. This may take several minutes.`,
            level: 'INFO'
          });
        }
        
        return {
          success: true,
          logs: simulatedLogs,
          vm: {
            id: vmDetails.id,
            name: vmDetails.name,
            status: vmDetails.status
          },
          simulated: true
        };
      }
    } catch (error: any) {
      console.error(`[getVMDeploymentLogs] Error mendapatkan log:`, error);
      
      return {
        success: false,
        message: error.message || 'Gagal mendapatkan log deployment',
        error: error
      };
    }
  }

  // Fungsi sederhana untuk deploy VM langsung mengikuti format Terraform
  async deployGCPVMWithTerraform(data: {
    name: string;
    credential_id: number;
    zone?: string;
    region?: string;
    machineType?: string;
    diskSizeGB?: number;
    tags?: string[];
    useSpot?: boolean;
  }): Promise<any> {
    try {
      console.log('[deployGCPVMWithTerraform] Memulai deployment VM dengan data:', data);
      
      // Pastikan credential_id adalah number
      const credentialId = typeof data.credential_id === 'string' ? 
        parseInt(data.credential_id as string, 10) : data.credential_id;
      
      // Siapkan parameter dasar
      const name = data.name;
      const zone = data.zone || 'us-central1-a';
      const region = data.region || zone.split('-').slice(0, 2).join('-');
      const machineType = data.machineType || 'e2-micro';
      const diskSizeGB = data.diskSizeGB || 10;
      const tags = data.tags || ['https-server'];
      const useSpot = data.useSpot !== undefined ? data.useSpot : true;
      
      // Map machineType ke CPU & memory berdasarkan tipe mesin GCP
      let cpu = 2;
      let memory = 4;
      
      // Machine type mapping
      switch (machineType) {
        case 'e2-micro':
          cpu = 1;
          memory = 1;
          break;
        case 'e2-small':
          cpu = 1;
          memory = 2;
          break;
        case 'e2-medium':
          cpu = 2;
          memory = 4;
          break;
        case 'e2-standard-2':
          cpu = 2;
          memory = 8;
          break;
        case 'e2-standard-4':
          cpu = 4;
          memory = 16;
          break;
        case 'e2-standard-8':
          cpu = 8;
          memory = 32;
          break;
        default:
          // Default untuk e2-small
          cpu = 1;
          memory = 2;
      }

      console.log(`[deployGCPVMWithTerraform] Machine type ${machineType} -> CPU: ${cpu}, Memory: ${memory}`);
      
      // Struktur payload yang sesuai dengan VMCreateExtended model di backend
      const deploymentData = {
        name: name,
        provider: 'gcp',
        region: region,
        credential_id: credentialId,
        instance_type: machineType,
        resources: {
          cpu: cpu,
          memory: memory,
          storage: diskSizeGB
        },
        network: {
          public_ip: true
        },
        // Tambahkan gcp_options dengan zone untuk memastikan backend mendapatkan zone yang benar
        gcp_options: {
          zone: zone,
          tags: tags,
          use_spot: useSpot
        }
      };
      
      console.log('[deployGCPVMWithTerraform] Payload final:', deploymentData);
      
      // Get auth token
      const token = localStorage.getItem('auth_token');
      if (!token) {
        throw new Error('Token autentikasi tidak ditemukan');
      }
      
      // Set headers
      const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      };
      
      // Buat request ke backend
      console.log('[deployGCPVMWithTerraform] Mengirim request ke http://localhost:8000/api/v1/vms/vms/');
      const response = await axios.post(
        'http://localhost:8000/api/v1/vms/vms/',
        deploymentData,
        {
          headers,
          timeout: 60000, // 60 seconds timeout
          withCredentials: true
        }
      );
      
      console.log('[deployGCPVMWithTerraform] Response:', response.status, response.data);
      
      return {
        success: true,
        vm: response.data,
        message: `VM ${name} berhasil dibuat`
      };
    } catch (error: any) {
      console.error('[deployGCPVMWithTerraform] Error:', error);
      
      let errorMessage = 'Gagal membuat VM';
      
      if (error.response) {
        console.error('[deployGCPVMWithTerraform] Response error:', {
          status: error.response.status,
          data: error.response.data
        });
        errorMessage = `Error ${error.response.status}: ${JSON.stringify(error.response.data)}`;
      } else if (error.request) {
        console.error('[deployGCPVMWithTerraform] Request error (no response)');
        errorMessage = 'Tidak ada respons dari server';
      } else {
        errorMessage = error.message;
      }
      
      return {
        success: false,
        message: errorMessage
      };
    }
  }

  async debugGCPServiceAccount(credentialId: number): Promise<any> {
    try {
      console.log('[debugGCPServiceAccount] Starting debug of GCP service account with credential ID:', credentialId);
      
      // Dapatkan detail kredensial
      const credentialDetails = await this.getCredentialDetails(credentialId);
      
      if (!credentialDetails || !credentialDetails.gcp_credentials) {
        return {
          status: 'error',
          message: 'Kredensial GCP tidak ditemukan'
        };
      }
      
      // Ekstrak service account key
      let serviceAccountKey;
      try {
        const gcp_creds = credentialDetails.gcp_credentials;
        
        if (typeof gcp_creds.gcp_service_account_json === 'string') {
          serviceAccountKey = JSON.parse(gcp_creds.gcp_service_account_json);
        } else {
          serviceAccountKey = gcp_creds.gcp_service_account_json;
        }
        
        console.log('[debugGCPServiceAccount] Successfully parsed service account key');
        
        // Log detail penting (non-sensitive)
        const saDetails = {
          type: serviceAccountKey.type,
          project_id: serviceAccountKey.project_id,
          client_id: serviceAccountKey.client_id,
          client_email: serviceAccountKey.client_email,
          auth_uri: serviceAccountKey.auth_uri,
          token_uri: serviceAccountKey.token_uri,
          private_key_id: serviceAccountKey.private_key_id,
          hasPrivateKey: !!serviceAccountKey.private_key,
          privateKeyLength: serviceAccountKey.private_key ? serviceAccountKey.private_key.length : 0
        };
        
        console.log('[debugGCPServiceAccount] Service Account Details:', saDetails);
        
        // Coba get temporary token untuk validasi
        try {
          console.log('[debugGCPServiceAccount] Attempting to get access token...');
          
          // Gunakan service API fetch langsung untuk mendapatkan token (tanpa melalui Terraform)
          // Enkode private key dan client email ke JSON
          const tokenEndpoint = `http://localhost:8000/api/v1/credentials/test-gcp-token`;
          const response = await fetch(tokenEndpoint, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            },
            body: JSON.stringify({
              credential_id: credentialId
            })
          });
          
          if (!response.ok) {
            const errorText = await response.text();
            console.error('[debugGCPServiceAccount] Failed to get token:', response.status, errorText);
            return {
              status: 'error',
              message: `Gagal mendapatkan token akses: ${response.status} ${errorText}`,
              serviceAccount: saDetails
            };
          }
          
          const tokenResult = await response.json();
          console.log('[debugGCPServiceAccount] Successfully got token response');
          
          return {
            status: 'success',
            message: 'Kredensial GCP valid dan token berhasil dibuat',
            serviceAccount: saDetails,
            token: {
              success: true,
              expires_in: tokenResult.expires_in
            }
          };
        } catch (tokenError) {
          console.error('[debugGCPServiceAccount] Error getting token:', tokenError);
          return {
            status: 'error',
            message: `Error saat mendapatkan token: ${tokenError instanceof Error ? tokenError.message : String(tokenError)}`,
            serviceAccount: saDetails
          };
        }
      } catch (parseError) {
        console.error('[debugGCPServiceAccount] Error parsing service account key:', parseError);
        return {
          status: 'error',
          message: `Error parsing service account key: ${parseError instanceof Error ? parseError.message : String(parseError)}`
        };
      }
    } catch (error) {
      console.error('[debugGCPServiceAccount] Error:', error);
      return {
        status: 'error',
        message: `Error tidak terduga: ${error instanceof Error ? error.message : String(error)}`
      };
    }
  }

  async updateGCPCredential(credentialId: number, serviceAccountKey: string | object, projectId?: string): Promise<any> {
    try {
      console.log(`[updateGCPCredential] Updating GCP credential ${credentialId}`);
      
      // Dapatkan detail kredensial untuk nama
      const credentialDetails = await this.getCredentialDetails(credentialId);
      
      if (!credentialDetails) {
        throw new Error('Kredensial tidak ditemukan');
      }
      
      // Pastikan service account key dalam format string JSON
      let serviceAccountKeyString: string;
      if (typeof serviceAccountKey === 'object') {
        serviceAccountKeyString = JSON.stringify(serviceAccountKey);
      } else {
        serviceAccountKeyString = serviceAccountKey;
      }
      
      // Validate service account key sebagai JSON
      try {
        JSON.parse(serviceAccountKeyString);
      } catch (e) {
        throw new Error('Service account key bukan JSON yang valid');
      }
      
      // Struktur data untuk update kredensial
      const updateData = {
        name: credentialDetails.name,
        type: "GCP",
        gcp_credentials: {
          gcp_service_account_json: serviceAccountKeyString,
          gcp_project_id: projectId || JSON.parse(serviceAccountKeyString).project_id
        }
      };
      
      // Kirim request update
      const endpoint = `http://localhost:8000/api/v1/credentials/credentials/${credentialId}`;
      const response = await fetch(endpoint, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(updateData)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to update credential: ${response.status} ${errorText}`);
      }
      
      const result = await response.json();
      return result;
    } catch (error: any) {
      console.error('[updateGCPCredential] Error:', error);
      throw error;
    }
  }
}

export default new TerraformService(); 