export enum EventType {
  // VM Events
  VM_CREATE = "vm_create",
  VM_START = "vm_start",
  VM_STOP = "vm_stop",
  VM_DELETE = "vm_delete",
  VM_STATUS_UPDATE = "vm_status_update",
  VM_UPDATE = "vm_update",

  // Credential Events
  CREDENTIAL_CREATE = "credential_create",
  CREDENTIAL_UPDATE = "credential_update",
  CREDENTIAL_DELETE = "credential_delete",
  CREDENTIAL_VALIDATE = "credential_validate",
}

export enum EventStatus {
  SUCCESS = "success",
  FAILED = "failed",
  PENDING = "pending",
  IN_PROGRESS = "in_progress",
}

export interface HistoryEvent {
  id: number;
  event_type: EventType;
  status: EventStatus;
  timestamp: string;
  user_id: number;
  vm_id?: number;
  credential_id?: number;
  parameters?: Record<string, any>;
  result?: Record<string, any>;
  error_message?: string;
  duration?: number;
  vm_name?: string; 
}

export interface HistoryEventListResponse {
  events: HistoryEvent[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
