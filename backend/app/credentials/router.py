from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query, Request, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import logging
import json
from app.database import get_db
from app.users.models import User
from app.auth.jwt import get_current_user
from app.credentials.models import (
    Credential, 
    CredentialType, 
    CredentialCreate, 
    CredentialResponse,
    CredentialListResponse,
    AWSCredentialCreate,
    GCPCredentials
)
from app.credentials.encryption import encrypt_credentials, decrypt_credentials, mask_sensitive_data
from app.credentials.service import CredentialService
import app.credentials.encryption as encryption

router = APIRouter(
    prefix="/credentials",
    tags=["credentials"],
    responses={404: {"description": "Not found"}},
)
logger = logging.getLogger(__name__)

@router.post("/", response_model=CredentialResponse)
def create_credential(
    credential: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Membuat kredensial baru untuk cloud provider
    """
    logger.info(f"Creating credential of type: {credential.type}")
    logger.debug(f"Credential data: {credential.model_dump(exclude_none=True)}")
    
    # Log kredensial yang masuk (amankan data sensitif)
    if credential.type == CredentialType.AWS and credential.aws_credentials:
        logger.info(f"AWS credential with keys: {list(credential.aws_credentials.model_dump().keys())}")
    elif credential.type == CredentialType.GCP and credential.gcp_credentials:
        logger.info(f"GCP credential with keys: {list(credential.gcp_credentials.keys())}")
        
        # Khusus untuk GCP, periksa jika service_account_key ada
        if credential.gcp_credentials.get('service_account_key'):
            logger.info("Service account key is present in the request")
    
    credential_service = CredentialService(db)
    
    try:
        # Gunakan model_dump() untuk pydantic v2, atau dict() untuk v1
        new_credential = credential_service.create_credential(
            user_id=current_user.id,
            credential_data=credential.model_dump(exclude_none=True)
        )
        logger.info(f"Successfully created credential with ID: {new_credential.id}")
        return new_credential
    except ValueError as e:
        logger.error(f"Invalid data for credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Error creating credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat membuat kredensial: {str(e)}"
        )

@router.get("/", response_model=CredentialListResponse)
def list_credentials(
    limit: int = Query(100, ge=1, le=1000, description="Jumlah maksimum kredensial yang dikembalikan"),
    offset: int = Query(0, ge=0, description="Jumlah kredensial yang dilewati untuk paginasi"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mendapatkan daftar kredensial milik pengguna
    """
    credential_service = CredentialService(db)
    
    credentials = credential_service.list_credentials(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )
    
    total = credential_service.count_credentials(current_user.id)
    
    return CredentialListResponse(credentials=credentials, total=total)

@router.get("/{credential_id}", response_model=CredentialResponse)
def get_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mendapatkan detail kredensial berdasarkan ID
    """
    credential_service = CredentialService(db)
    
    credential = credential_service.get_credential(
        credential_id=credential_id,
        user_id=current_user.id
    )
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kredensial dengan ID {credential_id} tidak ditemukan"
        )
    
    return credential

@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Menghapus kredensial berdasarkan ID
    """
    credential_service = CredentialService(db)
    
    try:
        credential_service.delete_credential(
            credential_id=credential_id,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat menghapus kredensial: {str(e)}"
        )

@router.put("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: int,
    credential_data: CredentialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a credential
    """
    credential_service = CredentialService(db)
    
    credential = credential_service.get_credential(
        credential_id=credential_id,
        user_id=current_user.id
    )
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    # Validate credential type matches existing
    if credential_data.type != credential.type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change credential type"
        )
    
    # Encrypt new credentials
    if credential.type == CredentialType.AWS:
        if not credential_data.aws_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AWS credentials required"
            )
        credentials_to_encrypt = {
            "aws_access_key_id": credential_data.aws_credentials.aws_access_key_id,
            "aws_secret_access_key": credential_data.aws_credentials.aws_secret_access_key,
            "aws_region": credential_data.aws_credentials.aws_region
        }
    elif credential.type == CredentialType.GCP:
        if not credential_data.gcp_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GCP credentials required"
            )
        credentials_to_encrypt = {
            "gcp_service_account_json": credential_data.gcp_credentials.gcp_service_account_json,
            "gcp_project_id": credential_data.gcp_credentials.gcp_project_id
        }
    
    encrypted_data = encrypt_credentials(credentials_to_encrypt)
    
    # Update credential
    credential.name = credential_data.name
    credential.encrypted_data = encrypted_data
    
    credential_service.update_credential(credential)
    
    return credential

@router.get("/{credential_id}/validate", response_model=dict)
async def validate_credential(
    credential_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate that a credential works with the cloud provider
    """
    credential_service = CredentialService(db)
    
    credential = credential_service.get_credential(
        credential_id=credential_id,
        user_id=current_user.id
    )
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    # Decrypt credentials
    try:
        decrypted_data = decrypt_credentials(credential.encrypted_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error decrypting credentials: {str(e)}"
        )
    
    # Menyiapkan log untuk debug
    logger.debug(f"Validating credential type: {credential.type}")
    logger.debug(f"Decrypted data keys: {decrypted_data.keys()}")
    
    # Validate with cloud provider
    try:
        if credential.type == CredentialType.AWS:
            # Code to validate AWS credentials
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
            
            try:
                # Cek kunci yang ada di data terenkripsi
                aws_access_key = decrypted_data.get('access_key') or decrypted_data.get('aws_access_key_id')
                aws_secret_key = decrypted_data.get('secret_key') or decrypted_data.get('aws_secret_access_key') 
                aws_region = decrypted_data.get('region') or decrypted_data.get('aws_region')
                
                if not aws_access_key:
                    return {"valid": False, "message": "Validation failed: 'aws_access_key_id'"}
                    
                if not aws_secret_key:
                    return {"valid": False, "message": "Validation failed: 'aws_secret_access_key'"}
                    
                if not aws_region:
                    return {"valid": False, "message": "Validation failed: 'aws_region'"}
                
                logger.debug(f"Using AWS credentials with region: {aws_region}")
                
                # Buat sesi dengan kredensial
                session = boto3.Session(
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=aws_region
                )
                
                # Coba akses layanan EC2 untuk validasi
                ec2 = session.client('ec2')
                ec2.describe_regions()  # Ini akan gagal jika kredensial tidak valid
                
                return {"valid": True, "message": "Kredensial AWS berhasil divalidasi"}
                
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                error_message = e.response.get('Error', {}).get('Message', str(e))
                logger.error(f"AWS validation error: {error_code} - {error_message}")
                return {
                    "valid": False, 
                    "message": f"Validasi AWS gagal: {error_code} - {error_message}"
                }
            except NoCredentialsError:
                logger.error("AWS validation error: No credentials provided")
                return {
                    "valid": False,
                    "message": "Validasi AWS gagal: Kredensial tidak ditemukan"
                }
            except Exception as e:
                logger.error(f"Unexpected AWS validation error: {str(e)}")
                return {
                    "valid": False,
                    "message": f"Validasi AWS gagal: {str(e)}"
                }
            
        elif credential.type == CredentialType.GCP:
            # Code to validate GCP credentials
            from google.oauth2 import service_account
            from google.cloud import storage
            import json
            
            try:
                # Cek format kredensial GCP
                if 'gcp_service_account_json' in decrypted_data:
                    # Format lengkap dari file JSON
                    service_account_info = decrypted_data['gcp_service_account_json']
                else:
                    # Format dari input manual
                    service_account_info = {
                        "type": "service_account",
                        "project_id": decrypted_data.get('project_id'),
                        "private_key_id": decrypted_data.get('private_key_id'),
                        "private_key": decrypted_data.get('private_key'),
                        "client_email": decrypted_data.get('client_email'),
                        "client_id": decrypted_data.get('client_id'),
                        "auth_uri": decrypted_data.get('auth_uri', "https://accounts.google.com/o/oauth2/auth"),
                        "token_uri": decrypted_data.get('token_uri', "https://oauth2.googleapis.com/token"),
                        "auth_provider_x509_cert_url": decrypted_data.get('auth_provider_x509_cert_url', 
                                                        "https://www.googleapis.com/oauth2/v1/certs"),
                        "client_x509_cert_url": decrypted_data.get('client_x509_cert_url', "")
                    }
                
                # Validasi field-field penting
                for field in ['project_id', 'private_key', 'client_email']:
                    if not service_account_info.get(field):
                        return {"valid": False, "message": f"Validation failed: '{field}'"}
                
                # Buat kredensial dari informasi service account
                credentials = service_account.Credentials.from_service_account_info(service_account_info)
                
                # Validasi dengan mencoba mengakses layanan Storage
                storage_client = storage.Client(credentials=credentials, project=service_account_info['project_id'])
                # Coba list buckets (hanya mengecek koneksi)
                storage_client.list_buckets(max_results=1)
                
                return {"valid": True, "message": "Kredensial GCP berhasil divalidasi"}
                
            except Exception as e:
                logger.error(f"GCP validation error: {str(e)}")
                return {
                    "valid": False,
                    "message": f"Validasi GCP gagal: {str(e)}"
                }
        else:
            return {
                "valid": False,
                "message": f"Tipe kredensial tidak didukung: {credential.type}"
            }
    except Exception as e:
        logger.error(f"Unexpected error in credential validation: {str(e)}")
        return {
            "valid": False,
            "message": f"Validasi gagal: {str(e)}"
        }

@router.get("/{credential_id}/details", response_model=Dict[str, Any])
async def get_credential_details(
    credential_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get decrypted credential details for editing
    """
    credential_service = CredentialService(db)
    
    credential = credential_service.get_credential(
        credential_id=credential_id,
        user_id=current_user.id
    )
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Credential not found"
        )
    
    # Decrypt credentials
    try:
        decrypted_data = decrypt_credentials(credential.encrypted_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error decrypting credentials: {str(e)}"
        )
    
    # Prepare response based on credential type
    response = {
        "id": credential.id,
        "name": credential.name,
        "type": credential.type,
        "created_at": credential.created_at,
        "updated_at": credential.updated_at
    }
    
    if credential.type == CredentialType.AWS:
        response["aws_credentials"] = {
            "aws_access_key_id": decrypted_data.get("aws_access_key_id", ""),
            "aws_secret_access_key": decrypted_data.get("aws_secret_access_key", ""),
            "aws_region": decrypted_data.get("aws_region", "us-east-1")
        }
    elif credential.type == CredentialType.GCP:
        response["gcp_credentials"] = {
            "gcp_project_id": decrypted_data.get("gcp_project_id", ""),
            "gcp_service_account_json": decrypted_data.get("gcp_service_account_json", {})
        }
    
    return response

@router.post("/upload-gcp-json", response_model=Dict[str, Any])
async def upload_gcp_json(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload file JSON kredensial GCP
    
    Endpoint ini menerima file JSON kredensial GCP dan mengembalikan data yang dapat digunakan
    untuk membuat kredensial GCP melalui endpoint /credentials/
    """
    if not file.filename.lower().endswith('.json'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File harus berformat JSON"
        )
    
    try:
        # Baca konten file
        content = await file.read()
        
        # Log ukuran file untuk debugging
        logger.debug(f"File size: {len(content)} bytes")
        
        try:
            service_account_info = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File JSON tidak valid: {str(e)}"
            )
        
        # Log struktur JSON untuk debugging
        logger.debug(f"JSON structure keys: {list(service_account_info.keys())}")
        
        # Validasi format service account
        required_fields = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "auth_uri", "token_uri",
            "auth_provider_x509_cert_url", "client_x509_cert_url"
        ]
        
        missing_fields = [field for field in required_fields if field not in service_account_info]
        if missing_fields:
            logger.error(f"Missing fields in service account JSON: {missing_fields}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File JSON tidak valid. Field yang kurang: {', '.join(missing_fields)}"
            )
            
        if service_account_info["type"] != "service_account":
            logger.error(f"Invalid service account type: {service_account_info.get('type')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File JSON bukan service account key yang valid"
            )
        
        # Format data untuk pembuatan kredensial
        credential_data = {
            "gcp_project_id": service_account_info["project_id"],
            "gcp_service_account_json": service_account_info
        }
        
        logger.info("GCP JSON file successfully processed")
        
        return {
            "message": "File JSON berhasil diupload",
            "data": credential_data
        }
        
    except HTTPException:
        # Re-throw HTTP exceptions
        raise
    except Exception as e:
        logger.exception(f"Error processing GCP JSON file: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat memproses file: {str(e)}"
        )

@router.post("/test-gcp-token", response_model=Dict[str, Any])
async def test_gcp_token(
    request: Request,
    token_request: Dict[str, Any] = Body(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Menguji kredensial GCP dengan mengambil token akses sementara
    """
    logger.info(f"Testing GCP token with data: {token_request}")
    
    try:
        credential_id = token_request.get("credential_id")
        if not credential_id:
            raise HTTPException(status_code=400, detail="credential_id diperlukan")
        
        # Dapatkan credential
        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.user_id == user.id
        ).first()
        
        if not credential:
            raise HTTPException(status_code=404, detail=f"Credential dengan ID {credential_id} tidak ditemukan")
        
        if credential.type != "GCP":
            raise HTTPException(status_code=400, detail="Credential harus bertipe GCP")
        
        # Dekripsi kredensial
        service = CredentialService(db)
        decrypted_creds = service.get_decrypted_credential(credential_id, user.id)
        
        # Log kredensial yang telah didekripsi (tanpa nilai sensitif)
        logger.info(f"Decrypted credential keys: {list(decrypted_creds.keys())}")
        
        # Ekstrak service account key
        service_account_key = None
        
        # Format 1: Jika gcp_credentials ada
        if "gcp_credentials" in decrypted_creds:
            gcp_creds = decrypted_creds["gcp_credentials"]
            if "gcp_service_account_json" in gcp_creds:
                service_account_key = gcp_creds["gcp_service_account_json"]
                logger.info("Using Format 1 (from gcp_credentials)")
        
        # Format 2: Jika service_account_key ada langsung
        elif "service_account_key" in decrypted_creds:
            service_account_key = decrypted_creds["service_account_key"]
            logger.info("Using Format 2 (from service_account_key)")
        
        # Format 3: Jika gcp_service_account_json ada langsung
        elif "gcp_service_account_json" in decrypted_creds:
            service_account_key = decrypted_creds["gcp_service_account_json"]
            logger.info("Using Format 3 (direct gcp_service_account_json)")
        
        if not service_account_key:
            logger.error("Service account key not found in credentials")
            logger.error(f"Available credential keys: {list(decrypted_creds.keys())}")
            raise HTTPException(status_code=400, detail="Service account key tidak ditemukan dalam kredensial")
        
        # Pastikan service_account_key adalah objek dict
        if isinstance(service_account_key, str):
            try:
                logger.info("Converting service_account_key from string to JSON")
                service_account_key = json.loads(service_account_key)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing service_account_key: {str(e)}")
                raise HTTPException(status_code=400, detail=f"Service account key bukan JSON valid: {str(e)}")
        
        # Validasi service account key
        required_fields = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "auth_uri", "token_uri"
        ]
        
        missing_fields = [field for field in required_fields if field not in service_account_key]
        if missing_fields:
            logger.error(f"Missing required fields in service_account_key: {missing_fields}")
            raise HTTPException(
                status_code=400, 
                detail=f"Service account key tidak lengkap. Field yang kurang: {', '.join(missing_fields)}"
            )
        
        # Log detail service account key (kecuali private key)
        logger.info(f"Service account type: {service_account_key.get('type')}")
        logger.info(f"Service account project_id: {service_account_key.get('project_id')}")
        logger.info(f"Service account client_email: {service_account_key.get('client_email')}")
        
        # Coba dapatkan token akses
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
            
            # Credentials untuk GCP API
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            
            # Buat tempfile untuk menyimpan service account key
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp:
                try:
                    json.dump(service_account_key, temp)
                    temp.flush()
                    
                    # Buat credentials
                    credentials = service_account.Credentials.from_service_account_file(
                        temp.name, scopes=scopes
                    )
                    
                    # Refresh token - akan mengambil token baru
                    credentials.refresh(Request())
                    
                    logger.info("Successfully obtained GCP access token")
                    return {
                        "success": True,
                        "message": "Token berhasil diambil",
                        "token": "REDACTED",  # Jangan kirim token yang sebenarnya
                        "expires_in": credentials.expiry.isoformat() if credentials.expiry else None
                    }
                finally:
                    # Hapus file temporary
                    import os
                    try:
                        os.unlink(temp.name)
                    except Exception as e:
                        logger.warning(f"Error deleting temp file: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error getting GCP access token: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Gagal mendapatkan token akses: {str(e)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error tak terduga: {str(e)}")

@router.put("/credentials/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: int,
    credential_data: CredentialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Update kredensial yang sudah ada
    """
    logger.info(f"Updating credential {credential_id} for user {user.id}")
    
    # Cek apakah kredensial ada
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.user_id == user.id
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=404,
            detail=f"Credential dengan ID {credential_id} tidak ditemukan"
        )
    
    try:
        # Update data dasar
        credential.name = credential_data.name
        credential.type = credential_data.type
        
        # Ekstrak dan enkripsi data sensitif
        credential_dict = credential_data.dict(exclude_unset=True)
        
        if credential.type == CredentialType.AWS:
            # Handle AWS credentials
            aws_creds = credential_dict.get("aws_credentials")
            if aws_creds:
                encrypted_data = {
                    "aws_access_key_id": aws_creds.get("aws_access_key_id"),
                    "aws_secret_access_key": aws_creds.get("aws_secret_access_key"),
                    "aws_region": aws_creds.get("aws_region", "us-east-1")
                }
                credential.encrypted_data = encryption.encrypt_credentials(encrypted_data)
                
        elif credential.type == CredentialType.GCP:
            # Handle GCP credentials
            gcp_creds = credential_dict.get("gcp_credentials")
            if gcp_creds:
                encrypted_data = {}
                
                # Jika service account JSON ada
                if gcp_creds.get("gcp_service_account_json"):
                    # Simpan sebagai string JSON jika perlu
                    service_account_json = gcp_creds.get("gcp_service_account_json")
                    if isinstance(service_account_json, dict):
                        service_account_json = json.dumps(service_account_json)
                        
                    encrypted_data["gcp_service_account_json"] = service_account_json
                
                # Jika project ID ada
                if gcp_creds.get("gcp_project_id"):
                    encrypted_data["gcp_project_id"] = gcp_creds.get("gcp_project_id")
                    
                credential.encrypted_data = encryption.encrypt_credentials(encrypted_data)
        
        db.commit()
        db.refresh(credential)
        logger.info(f"Credential {credential_id} updated successfully")
        
        return credential
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating credential {credential_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error updating credential: {str(e)}"
        )