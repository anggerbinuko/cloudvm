from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum as SQLEnum, Boolean, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.database import Base
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime

class VMStatus(str, PyEnum):
    CREATING = "CREATING"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    STOPPING = "STOPPING"  # Added for AWS stopping state
    STARTING = "STARTING"  # Added for consistency
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"
    UNKNOWN = "UNKNOWN"  # Added for unknown states

class VMProvider(str, PyEnum):
    AWS = "aws"
    GCP = "gcp"
    
    @classmethod
    def _missing_(cls, value):
        # Coba konversi ke lowercase untuk menangani perbedaan case
        if isinstance(value, str):
            lowercase_value = value.lower()
            for member in cls:
                if member.value == lowercase_value:
                    return member
        return None

class VMPreset(str, PyEnum):
    LOW_COST = "low_cost"
    WEB_SERVER = "web_server"
    APP_SERVER = "app_server"
    CUSTOM = "custom"

class VM(Base):
    __tablename__ = "vms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    provider = Column(SQLEnum(VMProvider), index=True)  # AWS, GCP, dll
    region = Column(String)  # Region cloud
    instance_id = Column(String, nullable=True)  # ID instance di cloud provider
    instance_type = Column(String, nullable=True)  # Tipe instance (t2.micro, e2-medium, dll)
    status = Column(String, default=VMStatus.CREATING)  # Status VM
    public_ip = Column(String, nullable=True)  # IP publik
    private_ip = Column(String, nullable=True)  # IP privat
    credential_id = Column(Integer, ForeignKey("credentials.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    preset = Column(String, nullable=True)  # Preset yang digunakan (low_cost, web_server, dll)
    
    # Tambahan untuk sinkronisasi
    is_synced = Column(Boolean, default=False)  # Apakah VM ini hasil sinkronisasi dari cloud
    vm_metadata = Column(JSON, nullable=True)  # Metadata tambahan tentang VM (zona, detail lainnya)
    
    # Relationships
    user = relationship("User", back_populates="vms")
    credential = relationship("Credential", back_populates="vms")
    events = relationship("Event", back_populates="vm")

# Pydantic models for API
class VMBase(BaseModel):
    name: str
    provider: VMProvider
    instance_type: str
    region: str
    credential_id: int
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class VMCreate(VMBase):
    preset: Optional[str] = "custom"

class VMResponse(VMBase):
    id: int
    name: str
    provider: str
    region: str
    instance_id: Optional[str] = None
    instance_type: Optional[str] = None
    status: VMStatus
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    credential_id: int
    user_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    preset: Optional[str] = None
    is_synced: Optional[bool] = None
    vm_metadata: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    
    @classmethod
    def from_orm(cls, obj):
        # Pastikan provider selalu lower case
        if hasattr(obj, 'provider') and obj.provider:
            obj.provider = obj.provider.lower()
        return super().from_orm(obj)

class VMListResponse(BaseModel):
    vms: List[VMResponse]
    total: int
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

class VMResources(BaseModel):
    cpu: int = Field(ge=1, le=32, description="Jumlah vCPU")
    memory: int = Field(ge=1, le=64, description="Jumlah RAM dalam GB")
    storage: int = Field(ge=10, le=1000, description="Ukuran disk dalam GB")

class VMCreateExtended(VMBase):
    resources: VMResources
    network: Dict[str, Any] = Field(default_factory=dict, description="Konfigurasi jaringan")
    preset: Optional[str] = "custom"
    zone: Optional[str] = None
