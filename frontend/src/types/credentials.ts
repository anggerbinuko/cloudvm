export type CredentialType = 'aws' | 'gcp';

export interface Credential {
  id: number;
  name: string;
  type: CredentialType;
  encrypted_data?: string;
  created_at: string;
  updated_at: string | null;
  user_id: number;
}

// AWS credentials
export interface AWSCredentials {
  access_key: string;
  secret_key: string;
  region: string;
}

// GCP credentials
export interface GCPCredentials {
  project_id: string;
  private_key_id: string;
  private_key: string;
  client_email: string;
  client_id: string;
  auth_uri?: string;
  token_uri?: string;
  auth_provider_x509_cert_url?: string;
  client_x509_cert_url?: string;
  service_account_key?: any; // Service account key yang diupload dari JSON
}

// Create DTO for AWS
export interface AWSCredentialCreate {
  name: string;
  type: 'aws';
  access_key: string;
  secret_key: string;
  region: string;
}

// Create DTO for GCP
export interface GCPCredentialCreate {
  name: string;
  type: 'gcp';
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

// Create DTO generic
export interface CreateCredentialDto {
  name: string;
  type: CredentialType;
  aws_credentials?: AWSCredentials;
  gcp_credentials?: GCPCredentials;
  uploadedGcpData?: any; // Data dari hasil upload JSON GCP
}

// Update DTO
export interface UpdateCredentialDto {
  name?: string;
  type?: CredentialType;
  aws_credentials?: Partial<AWSCredentials>;
  gcp_credentials?: Partial<GCPCredentials>;
}

// Provider fields for form validation
export const providerFields = {
  'aws': {
    fields: ['access_key', 'secret_key', 'region'],
    label: 'AWS'
  },
  'gcp': {
    fields: ['project_id', 'private_key_id', 'private_key', 'client_email', 'client_id'],
    label: 'Google Cloud'
  }
}; 