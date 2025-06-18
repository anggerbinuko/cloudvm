from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
import json
from app.database import Base
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

# Import model VM
from app.vm.models import VM

logger = logging.getLogger(__name__)

class CredentialType(str, enum.Enum):
    AWS = "aws"
    GCP = "gcp"

class Credential(Base):
    __tablename__ = "credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(Enum(CredentialType))
    encrypted_data = Column(Text)  # Encrypted credentials
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship
    user = relationship("User", back_populates="credentials")
    vms = relationship("VM", back_populates="credential")
    events = relationship("Event", back_populates="credential")

class GCPServiceAccountKey(BaseModel):
    type: str = Field(default="service_account")
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    auth_uri: str = Field(default="https://accounts.google.com/o/oauth2/auth")
    token_uri: str = Field(default="https://oauth2.googleapis.com/token")
    auth_provider_x509_cert_url: str = Field(default="https://www.googleapis.com/oauth2/v1/certs")
    client_x509_cert_url: str
    universe_domain: Optional[str] = Field(default="googleapis.com")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "service_account",
                "project_id": "your-project-id",
                "private_key_id": "key-id",
                "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
                "client_email": "service-account@project-id.iam.gserviceaccount.com",
                "client_id": "client-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/service-account%40project-id.iam.gserviceaccount.com",
                "universe_domain": "googleapis.com"
            }
        }
    )

class GCPCredentials(BaseModel):
    gcp_project_id: str
    gcp_service_account_json: GCPServiceAccountKey

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "gcp_project_id": "your-project-id",
                "gcp_service_account_json": {
                    "type": "service_account",
                    "project_id": "your-project-id",
                    "private_key_id": "key-id",
                    "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
                    "client_email": "service-account@project-id.iam.gserviceaccount.com",
                    "client_id": "client-id"
                }
            }
        }
    )

    @field_validator("gcp_project_id")
    def validate_project_id(cls, v: str) -> str:
        if not v:
            raise ValueError("Project ID tidak boleh kosong")
        return v

    @field_validator("gcp_service_account_json")
    def validate_service_account(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id"
        ]
        
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Service account key harus memiliki field '{field}'")
        
        if v["type"] != "service_account":
            raise ValueError("Tipe service account harus 'service_account'")
            
        return v

# Pydantic models for API
class CredentialBase(BaseModel):
    name: str
    type: CredentialType

class AWSCredentialCreate(CredentialBase):
    type: CredentialType = CredentialType.AWS
    access_key: str
    secret_key: str
    region: str
    

class CredentialCreate(BaseModel):
    name: str
    type: CredentialType
    aws_credentials: Optional[AWSCredentialCreate] = None
    gcp_credentials: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "AWS Credential Saya",
                    "type": "aws",
                    "aws_credentials": {
                        "access_key": "AKIAIOSFODNN7EXAMPLE",
                        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                        "region": "us-east-1"
                    }
                },
                {
                    "name": "GCP Credential Saya",
                    "type": "gcp",
                    "gcp_credentials": {
                        "gcp_project_id": "your-project-id",
                        "gcp_service_account_json": {
                            "type": "service_account",
                            "project_id": "your-project-id",
                            "private_key_id": "key-id",
                            "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
                            "client_email": "service-account@project-id.iam.gserviceaccount.com",
                            "client_id": "client-id"
                        }
                    }
                }
            ]
        }
    )
    
    @model_validator(mode='after')
    def validate_credentials(self):
        # Log data untuk debugging
        logger.debug(f"Validating credential data: {self.name}, type: {self.type}")
        
        # AWS validation
        if self.type == CredentialType.AWS and not self.aws_credentials:
            raise ValueError("AWS credentials required when type is 'aws'")
        if self.type != CredentialType.AWS and self.aws_credentials:
            raise ValueError("AWS credentials should only be provided when type is 'aws'")
            
        # GCP validation
        if self.type == CredentialType.GCP and not self.gcp_credentials:
            raise ValueError("GCP credentials required when type is 'gcp'")
        
        if self.type == CredentialType.GCP and self.gcp_credentials:
            # Validasi struktur gcp_credentials
            if not isinstance(self.gcp_credentials, dict):
                raise ValueError("GCP credentials should be a dictionary")
                
            # Validasi field yang diperlukan
            if not self.gcp_credentials.get('gcp_project_id'):
                raise ValueError("GCP credentials must have gcp_project_id")
                
            if not self.gcp_credentials.get('gcp_service_account_json'):
                raise ValueError("GCP credentials must have gcp_service_account_json")
                
            # Validasi service_account_json
            service_account_json = self.gcp_credentials.get('gcp_service_account_json')
            if not isinstance(service_account_json, dict):
                if isinstance(service_account_json, str):
                    try:
                        # Coba parse jika string
                        self.gcp_credentials['gcp_service_account_json'] = json.loads(service_account_json)
                    except json.JSONDecodeError:
                        raise ValueError("gcp_service_account_json should be a valid JSON string or object")
                else:
                    raise ValueError("gcp_service_account_json should be a JSON object")
                
            # Validasi field wajib di service_account_json
            required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id"]
            service_account = self.gcp_credentials.get('gcp_service_account_json')
            
            if isinstance(service_account, dict):
                missing_fields = [field for field in required_fields if field not in service_account]
                if missing_fields:
                    raise ValueError(f"Service account json missing required fields: {', '.join(missing_fields)}")
                
                if service_account.get('type') != 'service_account':
                    raise ValueError("Service account type should be 'service_account'")
                
        if self.type != CredentialType.GCP and self.gcp_credentials:
            raise ValueError("GCP credentials should only be provided when type is 'gcp'")
            
        return self

class CredentialResponse(CredentialBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class CredentialListResponse(BaseModel):
    credentials: List[CredentialResponse]
    total: int