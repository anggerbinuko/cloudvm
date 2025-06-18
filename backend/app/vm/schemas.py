from typing import Optional
from pydantic import BaseModel, validator

class VMBase(BaseModel):
    name: str
    provider: str  # Ubah dari VMProvider menjadi str
    instance_id: str
    instance_type: str
    region: str
    
    @validator('provider')
    def normalize_provider(cls, v):
        if not v:
            return v
        # Normalize provider to lowercase
        return v.lower()

class SyncGCPVMRequest(BaseModel):
    """Request model untuk sinkronisasi VM GCP"""
    credential_id: int

class SyncAWSVMRequest(BaseModel):
    """
    Request schema untuk sinkronisasi VM AWS
    """
    credential_id: int

# ... existing code ... 