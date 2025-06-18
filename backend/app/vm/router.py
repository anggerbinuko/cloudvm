from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from app.database import get_db
from app.auth.jwt import get_current_user
from app.users.models import User
from app.vm.models import VM, VMCreate, VMResponse, VMListResponse, VMStatus, VMProvider
from app.vm.service import VMService
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vms",
    tags=["vms"],
    responses={404: {"description": "Not found"}},
)

class VMCreateExtended(VMCreate):
    # AWS specific
    ami_id: Optional[str] = None
    key_name: Optional[str] = None
    security_group_ids: Optional[List[str]] = None
    
    # GCP specific
    image: Optional[str] = None
    zone: Optional[str] = None

class VMActionResponse(BaseModel):
    status: str
    message: str

@router.get("/", response_model=VMListResponse)
def list_vms(
    limit: int = Query(100, ge=1, le=1000, description="Jumlah maksimum VM yang dikembalikan"),
    offset: int = Query(0, ge=0, description="Jumlah VM yang dilewati untuk paginasi"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mendapatkan daftar VM milik pengguna
    """
    vm_service = VMService(db)
    
    vms = vm_service.list_vms(
        user_id=current_user.id,
        limit=limit,
        offset=offset
    )
    
    total = vm_service.count_vms(current_user.id)
    
    return VMListResponse(vms=vms, total=total)

@router.get("/{vm_id}", response_model=VMResponse)
def get_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mendapatkan detail VM berdasarkan ID
    """
    vm_service = VMService(db)
    
    vm = vm_service.get_vm(
        vm_id=vm_id,
        user_id=current_user.id
    )
    
    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VM dengan ID {vm_id} tidak ditemukan"
        )
    
    return vm

@router.post("/", response_model=VMResponse)
def create_vm(
    vm_data: VMCreateExtended,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Membuat VM baru
    
    Request body:
    - name: Nama VM
    - provider: Provider cloud (aws/gcp)
    - region: Region cloud
    - credential_id: ID kredensial
    - resources: Spesifikasi resources
        - cpu: Jumlah vCPU (1-32)
        - memory: Jumlah RAM dalam GB (1-64)
        - storage: Ukuran disk dalam GB (10-1000)
    - network: Konfigurasi jaringan
    """
    vm_service = VMService(db)
    
    try:
        vm = vm_service.create_vm(
            user_id=current_user.id,
            vm_data=vm_data.dict()
        )
        return vm
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat membuat VM: {str(e)}"
        )

@router.post("/{vm_id}/start", response_model=VMResponse)
def start_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Memulai VM yang sedang berhenti
    """
    vm_service = VMService(db)
    
    try:
        vm = vm_service.start_vm(
            vm_id=vm_id,
            user_id=current_user.id
        )
        return vm
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat memulai VM: {str(e)}"
        )

@router.post("/{vm_id}/stop", response_model=VMResponse)
def stop_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Menghentikan VM yang sedang berjalan
    """
    vm_service = VMService(db)
    
    try:
        vm = vm_service.stop_vm(
            vm_id=vm_id,
            user_id=current_user.id
        )
        return vm
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat menghentikan VM: {str(e)}"
        )

@router.delete("/{vm_id}", response_model=VMActionResponse)
def delete_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Menghapus VM
    """
    vm_service = VMService(db)
    
    try:
        vm_service.delete_vm(
            vm_id=vm_id,
            user_id=current_user.id
        )
        return {"status": "success", "message": f"VM dengan ID {vm_id} berhasil dihapus"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat menghapus VM: {str(e)}"
        )

@router.put("/{vm_id}", response_model=VMResponse)
def update_vm(
    vm_id: int,
    vm_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mengupdate informasi VM
    """
    vm_service = VMService(db)
    
    try:
        vm = vm_service.update_vm(
            vm_id=vm_id,
            user_id=current_user.id,
            vm_data=vm_data
        )
        return vm
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat mengupdate VM: {str(e)}"
        )

@router.post("/gcp-instance-status", response_model=dict)
def get_gcp_instance_status(
    request_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mendapatkan status instance VM GCP
    
    Request body:
    - credential_id: ID kredensial GCP
    - project_id: ID project GCP
    - zone: Zone GCP
    - instance_name: Nama instance
    """
    vm_service = VMService(db)
    
    try:
        # Verifikasi data request
        required_fields = ["credential_id", "project_id", "zone", "instance_name"]
        for field in required_fields:
            if field not in request_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Field {field} diperlukan"
                )
        
        # Dapatkan status instance
        instance_status = vm_service.get_gcp_instance_status(
            user_id=current_user.id,
            credential_id=request_data["credential_id"],
            project_id=request_data["project_id"],
            zone=request_data["zone"],
            instance_name=request_data["instance_name"]
        )
        
        return instance_status
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Terjadi kesalahan saat mendapatkan status instance: {str(e)}"
        )

@router.post("/sync-gcp", response_model=VMActionResponse)
def sync_gcp_vms(
    credential_info: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Melakukan sinkronisasi VM dengan GCP
    
    Request body:
    - credential_id: ID kredensial GCP
    """
    vm_service = VMService(db)
    
    try:
        # Pastikan credential_id ada dalam request
        if not credential_info or "credential_id" not in credential_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="credential_id diperlukan dalam request"
            )
            
        credential_id = credential_info["credential_id"]
        
        # Lakukan sinkronisasi
        result = vm_service.sync_gcp_vms(
            user_id=current_user.id,
            credential_id=credential_id
        )
        
        # Buat pesan yang lebih informatif
        updated_count = result.get('updated_count', 0)
        created_count = result.get('created_count', 0)
        deleted_count = result.get('deleted_count', 0)
        duration = result.get('duration_seconds', 0)
        
        message = f"Berhasil menyinkronkan VM dengan GCP"
        
        # Hanya tambahkan informasi yang relevan
        parts = []
        if updated_count > 0:
            parts.append(f"{updated_count} diperbarui")
        if created_count > 0:
            parts.append(f"{created_count} ditambahkan")
        if deleted_count > 0:
            parts.append(f"{deleted_count} dihapus")
            
        if parts:
            message += ": " + ", ".join(parts)
            
        message += f" (waktu: {duration} detik)"
        
        return VMActionResponse(
            status="success",
            message=message
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyinkronkan VM: {str(e)}"
        )

@router.post("/sync-aws")
def sync_aws_vms(
    credential_info: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Melakukan sinkronisasi VM dengan AWS
    
    Request body:
    - credential_id: ID kredensial AWS
    """
    try:
        credential_id = credential_info.get("credential_id")
        if not credential_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="credential_id harus disediakan"
            )
            
        vm_service = VMService(db)
        result = vm_service.sync_aws_vms(current_user.id, credential_id)
        
        return {
            "status": "success",
            "message": f"Berhasil sinkronisasi {result['synced_count']} VM AWS" + 
                      (f" dan menghapus {result['deleted_count']} VM" if result['deleted_count'] > 0 else ""),
            "data": result
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error syncing AWS VMs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyinkronkan VM dengan AWS: {str(e)}"
        )

@router.post("/sync")
def sync_vms(
    request: Request,
    credential_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sync VMs with cloud provider (AWS or GCP)
    """
    try:
        vm_service = VMService(db)
        results = vm_service.sync_vms_with_provider(current_user.id, credential_id)
        return {"results": results}
    except Exception as e:
        logger.error(f"Error syncing VMs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kesalahan saat sinkronisasi VM: {str(e)}"
        )
