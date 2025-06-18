from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any
import json
import time
from datetime import datetime
import logging

from app.credentials.models import Credential, CredentialType
from app.credentials.encryption import encrypt_credentials, decrypt_credentials
from app.history.service import HistoryService
from app.history.models import EventType, EventStatus
from app.history.decorators import HistoryTracker, get_user_id, get_credential_id

logger = logging.getLogger(__name__)

class CredentialService:
    def __init__(self, db: Session):
        self.db = db
        self.history_service = HistoryService(db)
    
    @HistoryTracker(
        event_type=EventType.CREDENTIAL_CREATE,
        get_user_id=get_user_id,
        exclude_params=["aws_credentials", "gcp_credentials"]
    )
    def create_credential(self, user_id: int, credential_data: Dict[str, Any]) -> Credential:
        """
        Membuat kredensial baru
        """
        try:
            # Log data yang diterima untuk debugging
            logger.info(f"Creating credential with type: {credential_data.get('type')}")
            logger.debug(f"Credential data keys: {list(credential_data.keys())}")
            
            # Enkripsi data kredensial
            if credential_data["type"] == CredentialType.AWS:
                logger.debug("Processing AWS credential")
                if not credential_data.get("aws_credentials"):
                    raise ValueError("AWS credentials are required")
                    
                data_to_encrypt = {
                    "access_key": credential_data["aws_credentials"]["access_key"],
                    "secret_key": credential_data["aws_credentials"]["secret_key"],
                    "region": credential_data["aws_credentials"]["region"]
                }
            elif credential_data["type"] == CredentialType.GCP:
                logger.debug("Processing GCP credential")
                if not credential_data.get("gcp_credentials"):
                    raise ValueError("GCP credentials are required")
                
                # Log GCP credential structure
                logger.debug(f"GCP credential keys: {list(credential_data['gcp_credentials'].keys())}")
                
                # Cek jika gcp_service_account_json tersedia
                gcp_creds = credential_data["gcp_credentials"]
                gcp_project_id = gcp_creds.get("gcp_project_id")
                service_account_json = gcp_creds.get("gcp_service_account_json")
                
                if not gcp_project_id:
                    raise ValueError("GCP project ID is required")
                
                if not service_account_json:
                    raise ValueError("GCP service account JSON is required")
                
                # Log info tentang service_account_json untuk debugging
                logger.debug(f"Service account JSON type: {type(service_account_json)}")
                
                # Pastikan service_account_json adalah objek JSON
                if isinstance(service_account_json, str):
                    try:
                        logger.info("Converting service_account_json from string to JSON")
                        service_account_json = json.loads(service_account_json)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing service_account_json: {str(e)}")
                        raise ValueError("Format JSON kredensial GCP tidak valid")
                
                if not isinstance(service_account_json, dict):
                    logger.error(f"Service account JSON is not a dictionary: {type(service_account_json)}")
                    raise ValueError("Format service_account_json harus berupa objek JSON")
                
                # Validasi field yang diperlukan
                required_fields = [
                    "type", "project_id", "private_key_id", "private_key",
                    "client_email", "client_id"
                ]
                
                missing_fields = [field for field in required_fields if field not in service_account_json]
                if missing_fields:
                    logger.error(f"Missing required fields in service_account_json: {missing_fields}")
                    raise ValueError(f"Service account JSON tidak lengkap. Field yang kurang: {', '.join(missing_fields)}")
                
                # Data untuk dienkripsi
                data_to_encrypt = {
                    "gcp_project_id": gcp_project_id,
                    "gcp_service_account_json": service_account_json
                }
                
            else:
                logger.error(f"Unsupported credential type: {credential_data['type']}")
                raise ValueError(f"Tipe kredensial tidak didukung: {credential_data['type']}")
            
            logger.debug(f"Data to encrypt keys: {list(data_to_encrypt.keys())}")
            encrypted_data = encrypt_credentials(data_to_encrypt)
            
            # Buat kredensial di database
            credential = Credential(
                name=credential_data["name"],
                type=credential_data["type"],
                encrypted_data=encrypted_data,
                user_id=user_id
            )
            
            self.db.add(credential)
            self.db.commit()
            self.db.refresh(credential)
            
            logger.info(f"Credential created successfully with ID: {credential.id}")
            return credential
            
        except Exception as e:
            # Rollback transaksi database jika terjadi error
            self.db.rollback()
            
            # Log error untuk debugging
            logger.error(f"Error creating credential: {str(e)}")
            
            # Re-raise exception untuk ditangani oleh router
            raise
    
    def get_credential(self, credential_id: int, user_id: int) -> Optional[Credential]:
        """
        Mendapatkan kredensial berdasarkan ID
        """
        return self.db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.user_id == user_id
        ).first()
    
    def get_credential_by_provider(self, user_id: int, provider: str) -> Optional[Credential]:
        """
        Mendapatkan kredensial berdasarkan provider (normalisasi ke lowercase)
        """
        # Normalize provider
        if provider:
            provider = provider.lower()
            
        # Provider mapping untuk mendukung berbagai nama
        provider_mapping = {
            "aws": CredentialType.AWS,
            "amazon": CredentialType.AWS,
            "amazon web services": CredentialType.AWS,
            "gcp": CredentialType.GCP,
            "google": CredentialType.GCP,
            "google cloud": CredentialType.GCP,
            "google cloud platform": CredentialType.GCP
        }
        
        # Konversi ke enum type yang sesuai
        credential_type = provider_mapping.get(provider)
        if not credential_type:
            return None
            
        return self.db.query(Credential).filter(
            Credential.user_id == user_id,
            Credential.type == credential_type
        ).first()
    
    def get_decrypted_credential(self, credential_id: int, user_id: int, decrypt_data: bool = True) -> Dict[str, Any]:
        """
        Mendapatkan kredensial yang didekripsi
        
        Args:
            credential_id: ID kredensial
            user_id: ID pengguna
            decrypt_data: Boolean untuk mendekripsi data atau tidak
            
        Returns:
            Credential yang didekripsi dalam bentuk dictionary
        """
        logger.info(f"Getting decrypted credential for ID {credential_id}, user {user_id}, decrypt: {decrypt_data}")
        
        # Dapatkan credential dari database
        credential = self.get_credential(credential_id, user_id)
        
        if not credential:
            logger.error(f"Credential with ID {credential_id} not found for user {user_id}")
            raise ValueError(f"Credential with ID {credential_id} not found")
        
        # Buat base credential info
        credential_info = {
            "id": credential.id,
            "name": credential.name,
            "type": credential.type,
            "created_at": credential.created_at,
            "updated_at": credential.updated_at
        }
        
        # Jika perlu decrypt, tambahkan data yang didekripsi
        if decrypt_data and credential.encrypted_data:
            try:
                decrypted_data = decrypt_credentials(credential.encrypted_data)
                logger.info(f"Credential {credential_id} decrypted successfully")
                
                if credential.type == CredentialType.AWS:
                    # Format AWS credentials
                    aws_creds = json.loads(decrypted_data) if isinstance(decrypted_data, str) else decrypted_data
                    credential_info.update({
                        "aws_access_key_id": aws_creds.get("access_key"),
                        "aws_secret_access_key": aws_creds.get("secret_key"),
                        "aws_region": aws_creds.get("region")
                    })
                elif credential.type == CredentialType.GCP:
                    # Format GCP credentials
                    # Pastikan decrypted_data adalah JSON string atau dict
                    try:
                        if isinstance(decrypted_data, str):
                            gcp_creds = json.loads(decrypted_data)
                            logger.info("Successfully parsed decrypted_data as JSON string")
                        elif isinstance(decrypted_data, dict):
                            gcp_creds = decrypted_data
                            logger.info("Using decrypted_data directly as dict")
                        else:
                            logger.error(f"Unexpected type for decrypted_data: {type(decrypted_data)}")
                            raise ValueError(f"Unexpected type for decrypted_data: {type(decrypted_data)}")
                    
                        # Log struktur untuk debugging
                        logger.info(f"GCP credential structure: {list(gcp_creds.keys())}")
                        
                        # Ekstrak service account json dan project id
                        gcp_project_id = gcp_creds.get("gcp_project_id")
                        service_account_json = gcp_creds.get("gcp_service_account_json")
                        
                        if not gcp_project_id and service_account_json:
                            # Fallback: Ambil project_id dari service_account_json jika tidak tersedia langsung
                            gcp_project_id = service_account_json.get("project_id")
                            logger.info(f"Using project_id from service_account_json: {gcp_project_id}")
                        
                        # Tambahkan ke credential_info
                        credential_info.update({
                            "gcp_credentials": {
                                "gcp_project_id": gcp_project_id,
                                "gcp_service_account_json": service_account_json
                            }
                        })
                        
                        # Log untuk memastikan project_id diambil dengan benar
                        logger.info(f"Final GCP project_id: {credential_info['gcp_credentials']['gcp_project_id']}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding decrypted_data as JSON: {str(e)}")
                        raise ValueError(f"Invalid JSON format in decrypted credential: {str(e)}")
                
                # Tambahkan raw decrypted data jika dibutuhkan oleh fungsi lain
                credential_info["decrypted_data"] = decrypted_data
                
            except Exception as e:
                logger.error(f"Error decrypting credential {credential_id}: {str(e)}")
                raise ValueError(f"Error decrypting credential: {str(e)}")
        
        logger.info(f"Returning credential info for ID {credential_id}")
        return credential_info
    
    def list_credentials(self, user_id: int, limit: int = 100, offset: int = 0) -> List[Credential]:
        """
        Mendapatkan daftar kredensial milik pengguna
        """
        return self.db.query(Credential).filter(
            Credential.user_id == user_id
        ).limit(limit).offset(offset).all()
    
    def count_credentials(self, user_id: int) -> int:
        """
        Menghitung jumlah kredensial milik pengguna
        """
        return self.db.query(Credential).filter(
            Credential.user_id == user_id
        ).count()
    
    @HistoryTracker(
        event_type=EventType.CREDENTIAL_DELETE,
        get_user_id=get_user_id,
        get_credential_id=get_credential_id
    )
    def delete_credential(self, credential_id: int, user_id: int) -> bool:
        """
        Menghapus kredensial
        """
        credential = self.get_credential(credential_id, user_id)
        if not credential:
            raise ValueError(f"Kredensial dengan ID {credential_id} tidak ditemukan")
        
        try:
            # Periksa apakah kredensial sedang digunakan oleh VM
            vm_count = self.db.query(Credential).join(
                Credential.vms
            ).filter(
                Credential.id == credential_id
            ).count()
            
            if vm_count > 0:
                raise ValueError(f"Kredensial sedang digunakan oleh {vm_count} VM. Hapus VM terlebih dahulu.")
            
            # Hapus kredensial dari database
            self.db.delete(credential)
            self.db.commit()
            
            return True
            
        except Exception as e:
            # Rollback transaksi database jika terjadi error
            self.db.rollback()
            
            # Re-raise exception untuk ditangani oleh router
            raise 