from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.vm.service import VMService
from app.vm.schemas import SyncGCPVMRequest, SyncAWSVMRequest
from app.auth.security import get_current_user
from app.user.models import User
from app.database import get_db
from app.utils.logger import logger

router = APIRouter()

@router.post("/sync-aws", response_model=Dict[str, Any])
async def sync_aws_vms(
    request: SyncAWSVMRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sinkronisasi VM dari AWS ke database.
    """
    vm_service = VMService(db)
    try:
        result = vm_service.sync_aws_vms(
            user_id=current_user.id,
            credential_id=request.credential_id
        )
        return {
            "status": "success",
            "message": f"Berhasil sinkronisasi {result['synced_count']} VM AWS" + 
                      (f" dan menghapus {result['deleted_count']} VM" if result['deleted_count'] > 0 else ""),
            "data": result
        }
    except Exception as e:
        logger.error(f"Error syncing AWS VMs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menyinkronkan VM dengan AWS: {str(e)}"
        )

@router.post("/sync-gcp", response_model=Dict[str, Any])
async def sync_gcp_vms(
    request: SyncGCPVMRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Sinkronisasi VM dari GCP ke database.
    """
    vm_service = VMService(db)
    try:
        result = vm_service.sync_gcp_vms(
            user_id=current_user.id,
            credential_id=request.credential_id
        )
        return result
    except Exception as e:
        logger.error(f"Error syncing GCP VMs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error sinkronisasi VM GCP: {str(e)}"
        )

@router.post("/{vm_id}/start", response_model=Dict[str, Any])
async def start_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start a VM instance
    """
    vm_service = VMService(db)
    try:
        vm = vm_service.start_vm(vm_id=vm_id, user_id=current_user.id)
        return {
            "status": "success",
            "message": f"VM {vm.name} berhasil dimulai",
            "data": vm
        }
    except Exception as e:
        logger.error(f"Error starting VM: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Gagal memulai VM: {str(e)}"
        )

@router.post("/{vm_id}/stop", response_model=Dict[str, Any])
async def stop_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stop a VM instance
    """
    vm_service = VMService(db)
    try:
        vm = vm_service.stop_vm(vm_id=vm_id, user_id=current_user.id)
        return {
            "status": "success",
            "message": f"VM {vm.name} berhasil dihentikan",
            "data": vm
        }
    except Exception as e:
        logger.error(f"Error stopping VM: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menghentikan VM: {str(e)}"
        )

@router.get("/{vm_id}/ssh-key")
async def get_ssh_key(
    vm_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get SSH private key for a VM"""
    try:
        vm_service = VMService(db)
        private_key = vm_service.get_ssh_key(vm_id=vm_id, user_id=current_user.id)
        
        return Response(
            content=private_key,
            media_type="application/x-pem-file",
            headers={
                "Content-Disposition": f'attachment; filename="vm-{vm_id}-private-key.pem"'
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.delete("/{vm_id}", response_model=Dict[str, Any])
async def delete_vm(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a VM instance
    """
    vm_service = VMService(db)
    try:
        vm = vm_service.delete_vm(vm_id=vm_id, user_id=current_user.id)
        return {
            "status": "success",
            "message": f"VM berhasil dihapus",
            "data": vm
        }
    except Exception as e:
        logger.error(f"Error deleting VM: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Gagal menghapus VM: {str(e)}"
        )