import os
import json
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
import logging
import time
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import func
import re
from slugify import slugify
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import base64

from app.vm.models import VM, VMStatus, VMProvider
from app.credentials.models import Credential, CredentialType
from app.credentials.encryption import decrypt_credentials
from app.vm.aws_manager import AwsVmManager
from app.vm.gcp_manager import GcpVmManager
from app.vm.terraform_manager import TerraformManager
from app.config import settings
from app.credentials.service import CredentialService
from app.history.service import HistoryService
from app.history.models import EventType, EventStatus
from app.history.decorators import HistoryTracker, get_user_id, get_vm_id, get_credential_id
import boto3

logger = logging.getLogger(__name__)

def normalize_provider(provider: Optional[str]) -> Optional[str]:
    """
    Normalisasi provider ke lowercase dan menangani nilai None
    """
    if not provider:
        return None
    return provider.lower()

def normalize_name(name: str, provider: str) -> str:
    """
    Normalize VM name according to provider requirements
    """
    if provider.lower() == "gcp":
        # Convert to lowercase and replace spaces/special chars with hyphens
        normalized = slugify(name, separator="-")
        # Ensure it starts with a letter (GCP requirement)
        if not re.match('^[a-z]', normalized):
            normalized = f"vm-{normalized}"
        # Ensure it's not longer than 63 characters
        if len(normalized) > 63:
            normalized = normalized[:63]
        # Ensure it doesn't end with a hyphen
        normalized = normalized.rstrip('-')
        return normalized
    return name

class VMService:
    def __init__(self, db: Session):
        """
        Inisialisasi VM Service
        
        Args:
            db: Session database
        """
        self.db = db
        self.aws_manager = None
        self.gcp_manager = None
        self.terraform_manager = TerraformManager(os.path.join(settings.TERRAFORM_PATH))
        self.credential_service = CredentialService(db)
        self.history_service = HistoryService(db)
    
    def _get_credential(self, credential_id: int, user_id: int) -> Dict[str, Any]:
        """
        Mendapatkan dan mendekripsi kredensial dari database
        """
        return self.credential_service.get_decrypted_credential(credential_id, user_id)
    
    def _get_aws_manager(self, credentials: Dict[str, Any]) -> AwsVmManager:
        """
        Mendapatkan AWS Manager
        
        Args:
            credentials: Kredensial AWS
            
        Returns:
            Instance AWS Manager
        """
        return AwsVmManager(credentials)
    
    def _get_gcp_manager(self, credentials: Dict[str, Any]) -> GcpVmManager:
        """
        Mendapatkan GCP Manager
        
        Args:
            credentials: Kredensial GCP
            
        Returns:
            Instance GCP Manager
        """
        return GcpVmManager(credentials)
    
    @HistoryTracker(
        event_type=EventType.VM_CREATE,
        get_user_id=get_user_id,
        get_vm_id=get_vm_id,
        get_credential_id=get_credential_id
    )
    def create_vm(self, vm_data: Dict[str, Any], user_id: int) -> VM:
        """
        Membuat VM baru dan melakukan deployment ke cloud provider
        
        Args:
            vm_data: Data VM yang akan dibuat
            user_id: ID pengguna
            
        Returns:
            VM yang telah dibuat
        """
        # Pastikan provider dinormalisasi ke lowercase
        if "provider" in vm_data:
            vm_data["provider"] = normalize_provider(vm_data["provider"])
        
        # Dapatkan kredensial
        if "credential_id" not in vm_data:
            raise ValueError("credential_id harus disediakan")
        
        # Konversi preset jika tersedia dan menggunakan format dengan hyphen
        if "preset" in vm_data:
            preset = vm_data.get("preset")
            # Konversi format preset dari hyphen ke underscore
            if preset == "low-cost":
                preset = "low_cost"
                logger.info(f"Converting preset from 'low-cost' to 'low_cost'")
            elif preset == "web-server":
                preset = "web_server"
                logger.info(f"Converting preset from 'web-server' to 'web_server'")
            elif preset == "app-server":
                preset = "app_server"
                logger.info(f"Converting preset from 'app-server' to 'app_server'")
            
            # Update vm_data dengan preset yang sudah dikonversi
            vm_data["preset"] = preset
            
        # Log vm_data
        logger.info(f"Creating VM with data: {vm_data}")
        
        # Buat record VM
        logger.info(f"Creating VM with data: {vm_data}")
        logger.info(f"User ID: {user_id}")
        
        # Dapatkan kredensial
        try:
            logger.info(f"Fetching credential with ID: {vm_data['credential_id']}")
            credentials = self._get_credential(vm_data['credential_id'], user_id)
            logger.info(f"Successfully fetched credential with type: {credentials.get('type')}")
            
            # Log credential keys untuk debugging (tanpa nilai sensitif)
            cred_keys = list(credentials.keys())
            logger.info(f"Credential keys: {cred_keys}")
            
            if 'service_account_key' in credentials and isinstance(credentials['service_account_key'], dict):
                sa_keys = list(credentials['service_account_key'].keys())
                logger.info(f"Service account key fields: {sa_keys}")
                
                if 'project_id' in credentials['service_account_key']:
                    logger.info(f"Project ID in credential: {credentials['service_account_key']['project_id']}")
                else:
                    logger.warning("Project ID not found in service_account_key")
        except Exception as e:
            logger.error(f"Error retrieving credential: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error retrieving credential: {str(e)}")
            
        # Buat VM
        vm_name = normalize_name(vm_data['name'], vm_data['provider'])
        vm = VM(
            name=vm_name,
            provider=vm_data['provider'],
            region=vm_data['region'],
            instance_type=vm_data.get('instance_type', 't2.micro' if vm_data['provider'] == VMProvider.AWS else 'e2-micro'),
            status=VMStatus.CREATING,  # Langsung set ke CREATING
            user_id=user_id,
            credential_id=vm_data['credential_id'],
            preset=vm_data.get('preset', 'custom')  # Tambahkan preset ke VM
        )
        
        self.db.add(vm)
        self.db.commit()
        logger.info(f"Created VM record with ID: {vm.id}")
        
        try:
            # Deploy menggunakan Terraform
            if vm_data['provider'] == VMProvider.AWS:
                logger.info(f"Deploying AWS VM {vm.id} using Terraform")
                
                # Log AWS-specific data
                if 'ami_id' in vm_data:
                    logger.info(f"Using AMI ID: {vm_data['ami_id']}")
                if 'key_name' in vm_data:
                    logger.info(f"Using key name: {vm_data['key_name']}")
                
                # Log credential keys for debugging (without sensitive values)
                logger.info(f"Available credential keys: {list(credentials.keys())}")
                logger.info(f"AWS region from credentials: {credentials.get('aws_region')}")
                logger.info(f"Has access key: {bool(credentials.get('aws_access_key_id'))}")
                logger.info(f"Has secret key: {bool(credentials.get('aws_secret_access_key'))}")
                
                result = self.terraform_manager.apply_aws(
                    vm_data,
                    credentials,
                    vm.id
                )
                logger.info(f"AWS deployment result for VM {vm.id}: {result}")
                
                # Update instance ID dan IP jika ada
                if result and 'instance_id' in result:
                    vm.instance_id = result['instance_id']
                    vm.public_ip = result.get('public_ip')
                    vm.private_ip = result.get('private_ip')
                    logger.info(f"Updated VM {vm.id} with instance ID: {vm.instance_id}, Public IP: {vm.public_ip}")
                    
            elif vm_data['provider'] == VMProvider.GCP:
                logger.info(f"Deploying GCP VM {vm.id} using Terraform")
                
                # Log GCP-specific data
                if 'zone' in vm_data:
                    logger.info(f"Using zone: {vm_data['zone']}")
                else:
                    logger.info(f"Zone not specified, will derive from region: {vm_data['region']}")
                    
                if 'image' in vm_data:
                    logger.info(f"Using image: {vm_data['image']}")
                else:
                    logger.info("Using default Debian image")
                
                # Tambahkan resources ke vm_data
                if 'resources' in vm_data:
                    logger.info(f"Using resources: {vm_data['resources']}")
                
                # Log dan validasi preset
                preset = vm_data.get('preset', 'custom')
                # Konversi format preset dari hyphen ke underscore
                if preset == "low-cost":
                    preset = "low_cost"
                elif preset == "web-server":
                    preset = "web_server"
                elif preset == "app-server":
                    preset = "app_server"
                logger.info(f"Using preset template: {preset} (converted from {vm_data.get('preset', 'custom')})")

                # Update vm_data dengan preset yang sudah dikonversi
                vm_data['preset'] = preset
                
                result = self.terraform_manager.apply_gcp(
                    vm_data,
                    credentials,
                    vm.id
                )
                logger.info(f"GCP deployment result for VM {vm.id}: {result}")
                
                # Update instance ID dan IP jika ada
                if result and 'instance_id' in result:
                    vm.instance_id = result['instance_id']
                    vm.public_ip = result.get('public_ip')
                    vm.private_ip = result.get('private_ip')
                    logger.info(f"Updated VM {vm.id} with instance ID: {vm.instance_id}, Public IP: {vm.public_ip}")
                    
            else:
                logger.error(f"Unsupported provider: {vm_data['provider']}")
                raise ValueError(f"Unsupported provider: {vm_data['provider']}")
                
            # Update status VM
            vm.status = VMStatus.RUNNING
            
            # Update VM metadata
            self._update_vm_metadata(vm, vm_data)
            
            self.db.commit()
            logger.info(f"VM {vm.id} successfully deployed and running")
            
        except Exception as e:
            logger.error(f"Error deploying VM {vm.id}: {str(e)}")
            # Update status ke ERROR
            vm.status = VMStatus.FAILED
            self.db.commit()
            
            # Raise exception untuk dihandle di router
            raise HTTPException(status_code=500, detail=f"Failed to deploy VM: {str(e)}")
            
        # Update metadata VM
        self._update_vm_metadata(vm, vm_data)
        
        return vm
    
    @HistoryTracker(
        event_type=EventType.VM_STATUS_UPDATE,
        get_user_id=get_user_id,
        get_vm_id=get_vm_id
    )
    def get_vm(self, vm_id: int, user_id: int) -> Optional[VM]:
        """
        Mendapatkan detail VM dan memperbarui statusnya dari cloud jika VM sedang berjalan
        """
        vm = self.db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
        
        if not vm:
            return None
        
        # Jika VM sedang berjalan, refresh status dari cloud
        if vm.status == VMStatus.RUNNING:
            try:
                # Dapatkan kredensial yang didekripsi
                credentials = self._get_credential(vm.credential_id, user_id)
                
                # Periksa status VM di cloud berdasarkan provider
                if vm.provider == VMProvider.AWS:
                    # Implementasi pengecekan status AWS
                    pass
                elif vm.provider == VMProvider.GCP:
                    # Implementasi pengecekan status GCP
                    pass
                
            except Exception as e:
                logger.error(f"Error saat memeriksa status VM: {str(e)}")
        
        return vm
    
    def list_vms(self, user_id: int, provider: Optional[str] = None, credential_id: Optional[int] = None, 
                limit: Optional[int] = None, offset: Optional[int] = None) -> List[VM]:
        """
        List all VMs for a user, optionally filtered by provider and credential_id.
        
        Args:
            user_id: ID pengguna
            provider: Filter berdasarkan provider (optional)
            credential_id: Filter berdasarkan credential_id (optional)
            limit: Batasan jumlah hasil (optional)
            offset: Mulai dari index (optional)
            
        Returns:
            List VM yang sesuai dengan filter
        """
        # Buat query dasar
        query = self.db.query(VM).filter(VM.user_id == user_id)
        
        # Filter berdasarkan provider jika disediakan
        if provider:
            # Normalize provider to lowercase since VMProvider enum is case-sensitive
            provider = provider.lower()
            query = query.filter(VM.provider == provider)
        
        # Filter berdasarkan credential_id jika disediakan
        if credential_id:
            query = query.filter(VM.credential_id == credential_id)
        
        # Terapkan limit dan offset jika disediakan
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        return query.all()
    
    def count_vms(self, user_id: Optional[int] = None) -> int:
        """
        Menghitung jumlah VM yang dimiliki oleh pengguna
        
        Args:
            user_id: ID pengguna (opsional, jika None maka hitung semua VM)
            
        Returns:
            Jumlah VM
        """
        query = self.db.query(VM)
        
        if user_id is not None:
            query = query.filter(VM.user_id == user_id)
        
        return query.count()
    
    def count_vms_by_status(self, status: str, user_id: Optional[int] = None) -> int:
        """
        Menghitung jumlah VM berdasarkan status
        
        Args:
            status: Status VM (RUNNING, STOPPED, CREATING, FAILED)
            user_id: ID pengguna (opsional, jika None maka hitung semua VM)
            
        Returns:
            Jumlah VM dengan status tertentu
        """
        query = self.db.query(VM).filter(VM.status == status)
        
        if user_id is not None:
            query = query.filter(VM.user_id == user_id)
        
        return query.count()
    
    @HistoryTracker(
        event_type=EventType.VM_START,
        get_user_id=get_user_id,
        get_vm_id=get_vm_id
    )
    def start_vm(self, vm_id: int, user_id: int) -> VM:
        """
        Memulai VM yang sedang berhenti
        """
        vm = self.db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
        
        if not vm:
            raise ValueError(f"VM dengan ID {vm_id} tidak ditemukan")
            
        if vm.status == VMStatus.RUNNING:
            raise ValueError("VM sudah dalam keadaan berjalan")
            
        try:
            # Get credentials
            credentials = self._get_credential(vm.credential_id, user_id)
            
            if vm.provider == VMProvider.AWS:
                # Get AWS manager
                aws_manager = self._get_aws_manager(credentials)
                if not vm.instance_id:
                    raise ValueError("Instance ID tidak ditemukan")
                    
                # Start the instance
                aws_manager.start_instance(vm.instance_id)
                
            elif vm.provider == VMProvider.GCP:
                # Get GCP manager
                gcp_manager = self._get_gcp_manager(credentials)
                if not vm.instance_id:
                    raise ValueError("Instance ID tidak ditemukan")
                    
                # Start the instance
                gcp_manager.start_instance(vm.instance_id)
                
            else:
                raise ValueError(f"Provider tidak didukung: {vm.provider}")
                
            # Update VM status
            vm.status = VMStatus.RUNNING
            self.db.commit()
            
            return vm
            
        except Exception as e:
            logger.error(f"Error starting VM {vm_id}: {str(e)}")
            raise ValueError(f"Gagal memulai VM: {str(e)}")
            
    @HistoryTracker(
        event_type=EventType.VM_STOP,
        get_user_id=get_user_id,
        get_vm_id=get_vm_id
    )
    def stop_vm(self, vm_id: int, user_id: int) -> VM:
        """
        Menghentikan VM yang sedang berjalan
        """
        vm = self.db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
        
        if not vm:
            raise ValueError(f"VM dengan ID {vm_id} tidak ditemukan")
            
        if vm.status == VMStatus.STOPPED:
            raise ValueError("VM sudah dalam keadaan berhenti")
            
        try:
            # Get credentials
            credentials = self._get_credential(vm.credential_id, user_id)
            
            if vm.provider == VMProvider.AWS:
                # Get AWS manager
                aws_manager = self._get_aws_manager(credentials)
                if not vm.instance_id:
                    raise ValueError("Instance ID tidak ditemukan")
                    
                # Stop the instance
                aws_manager.stop_instance(vm.instance_id)
                
            elif vm.provider == VMProvider.GCP:
                # Get GCP manager
                gcp_manager = self._get_gcp_manager(credentials)
                if not vm.instance_id:
                    raise ValueError("Instance ID tidak ditemukan")
                    
                # Stop the instance
                gcp_manager.stop_instance(vm.instance_id)
                
            else:
                raise ValueError(f"Provider tidak didukung: {vm.provider}")
                
            # Update VM status
            vm.status = VMStatus.STOPPED
            self.db.commit()
            
            return vm
            
        except Exception as e:
            logger.error(f"Error stopping VM {vm_id}: {str(e)}")
            raise ValueError(f"Gagal menghentikan VM: {str(e)}")
            
    @HistoryTracker(
        event_type=EventType.VM_DELETE,
        get_user_id=get_user_id,
        get_vm_id=get_vm_id
    )
    def delete_vm(self, vm_id: int, user_id: int) -> VM:
        """
        Menghapus VM dari cloud dan database
        """
        vm = self.db.query(VM).filter(VM.id == vm_id, VM.user_id == user_id).first()
        
        if not vm:
            raise ValueError(f"VM dengan ID {vm_id} tidak ditemukan")
            
        try:
            # Get credentials
            credentials = self._get_credential(vm.credential_id, user_id)
            
            if vm.provider == VMProvider.AWS:
                # Get AWS manager
                aws_manager = self._get_aws_manager(credentials)
                if vm.instance_id:
                    try:
                        # Terminate the instance if it exists
                        aws_manager.terminate_instance(vm.instance_id)
                    except Exception as e:
                        # Check if it's a 404 error (instance not found)
                        if "404" in str(e) or "not found" in str(e).lower():
                            logger.warning(f"AWS VM {vm.instance_id} not found, proceeding with database deletion only")
                        else:
                            # Re-raise if it's not a 404 error
                            raise
                    
            elif vm.provider == VMProvider.GCP:
                # Get GCP manager
                gcp_manager = self._get_gcp_manager(credentials)
                if vm.instance_id:
                    try:
                        # Delete the instance if it exists
                        gcp_manager.delete_instance(vm.instance_id)
                    except Exception as e:
                        # Check if it's a 404 error (instance not found)
                        if "404" in str(e) or "not found" in str(e).lower():
                            logger.warning(f"GCP VM {vm.instance_id} not found, proceeding with database deletion only")
                        else:
                            # Re-raise if it's not a 404 error
                            raise
                    
            else:
                raise ValueError(f"Provider tidak didukung: {vm.provider}")
                
            # Delete VM from database
            self.db.delete(vm)
            self.db.commit()
            
            return vm
            
        except Exception as e:
            logger.error(f"Error deleting VM {vm_id}: {str(e)}")
            raise ValueError(f"Gagal menghapus VM: {str(e)}")
            
    @HistoryTracker(
        event_type=EventType.VM_UPDATE,
        get_user_id=get_user_id,
        get_vm_id=get_vm_id
    )
    def update_vm(self, vm_id: int, user_id: int, vm_data: Dict[str, Any]) -> VM:
        """
        Mengupdate informasi VM
        
        Args:
            vm_id: ID VM
            user_id: ID pengguna
            vm_data: Data yang akan diupdate
            
        Returns:
            VM yang telah diupdate
        """
        logger.info(f"Updating VM {vm_id} with data: {vm_data}")
        
        # Dapatkan VM
        vm = self.get_vm(vm_id, user_id)
        if not vm:
            logger.error(f"VM {vm_id} not found for user {user_id}")
            raise ValueError(f"VM dengan ID {vm_id} tidak ditemukan")
        
        # Update fields yang disediakan
        if 'status' in vm_data:
            vm.status = vm_data['status']
            logger.info(f"Updated VM {vm_id} status to {vm_data['status']}")
        
        if 'public_ip' in vm_data and vm_data['public_ip'] is not None:
            vm.public_ip = vm_data['public_ip']
            logger.info(f"Updated VM {vm_id} public IP to {vm_data['public_ip']}")
        
        if 'private_ip' in vm_data and vm_data['private_ip'] is not None:
            vm.private_ip = vm_data['private_ip']
            logger.info(f"Updated VM {vm_id} private IP to {vm_data['private_ip']}")
        
        if 'instance_id' in vm_data and vm_data['instance_id'] is not None:
            vm.instance_id = vm_data['instance_id']
            logger.info(f"Updated VM {vm_id} instance ID to {vm_data['instance_id']}")
        
        # Update VM di database
        self.db.commit()
        logger.info(f"VM {vm_id} successfully updated")
        
        return vm 

    def get_gcp_instance_status(
        self, 
        user_id: int, 
        credential_id: int, 
        project_id: str, 
        zone: str, 
        instance_name: str
    ) -> Dict[str, Any]:
        """
        Mendapatkan status instance GCP
        
        Args:
            user_id: ID pengguna
            credential_id: ID kredensial GCP
            project_id: ID project GCP
            zone: Zone GCP
            instance_name: Nama instance
            
        Returns:
            Status dan detail instance
        """
        logger.info(f"Getting GCP instance status for {instance_name} in {zone}")
        
        try:
            # Dapatkan kredensial yang didekripsi
            credentials = self._get_credential(credential_id, user_id)
            logger.info(f"Using credential ID {credential_id} for GCP instance status")
            
            # Inisialisasi GCP manager
            if not self.gcp_manager:
                self.gcp_manager = self._get_gcp_manager(credentials)
                logger.info("GCP manager initialized")
            
            # Dapatkan status instance
            instance = self.gcp_manager.get_instance(
                name=instance_name,
                zone=zone
            )
            
            if not instance:
                logger.error(f"Instance {instance_name} not found in zone {zone}")
                raise ValueError(f"Instance {instance_name} tidak ditemukan di zone {zone}")
            
            logger.info(f"Instance {instance_name} status: {instance.get('status')}")
            return instance
        except Exception as e:
            logger.error(f"Error getting GCP instance status: {str(e)}")
            raise 

    async def create_aws_vm(self, vm_data, credentials, user):
        try:
            # Buat VM dengan status pending
            vm = await self.create_vm_document(
                vm_data,
                "aws",
                user
            )

            # Jalankan Terraform dalam background task
            fastapi_app = self.server_instance.app
            fastapi_app.background_tasks.add_task(
                self.create_aws_vm_background,
                vm_data,
                vm,
                credentials
            )

            return vm
        except Exception as e:
            logger.error(f"Error creating AWS VM: {str(e)}")
            raise

    async def create_aws_vm_background(self, vm_data, vm, credentials):
        try:
            with await self.terraform_lock:
                # Log dan validasi preset
                preset = vm_data.get('preset', 'custom')
                # Konversi format preset dari hyphen ke underscore
                if preset == "low-cost":
                    preset = "low_cost"
                elif preset == "web-server":
                    preset = "web_server"
                elif preset == "app-server":
                    preset = "app_server"
                logger.info(f"Using preset template: {preset} (converted from {vm_data.get('preset', 'custom')})")

                # Update vm_data dengan preset yang sudah dikonversi
                vm_data['preset'] = preset
                
                result = self.terraform_manager.apply_aws(
                    vm_data,
                    credentials,
                    vm.id
                )
                logger.info(f"AWS deployment result for VM {vm.id}: {result}")
                
                # Update instance ID dan IP jika ada
                if result and 'instance_id' in result:
                    vm.instance_id = result['instance_id']
                    vm.public_ip = result.get('public_ip')
                    vm.private_ip = result.get('private_ip')
                    logger.info(f"Updated VM {vm.id} with instance ID: {vm.instance_id}, Public IP: {vm.public_ip}")
                    
        except Exception as e:
            logger.error(f"Error creating AWS VM: {str(e)}")
            raise 

    def sync_gcp_vms(self, user_id: int, credential_id: int = None) -> dict:
        """
        Sync VMs from GCP to database with optimized handling.
        
        Args:
            user_id: User ID
            credential_id: GCP credential ID (optional)
                
        Returns:
            Dict containing sync results
        """
        from app.credentials.models import Credential, CredentialType
        from app.credentials.service import CredentialService
        import time
        
        start_time = time.time()
        logger.info(f"Starting GCP VM synchronization for user {user_id}")
        
        updated_count = 0
        deleted_count = 0
        created_count = 0
        
        try:
            # If no specific credential provided, process all GCP credentials for the user
            if credential_id is None:
                logger.info(f"No specific credential provided, using all available GCP credentials")
                # Find all GCP credentials for the user
                credential_service = CredentialService(self.db)
                gcp_credentials = self.db.query(Credential).filter(
                    Credential.user_id == user_id,
                    Credential.type == CredentialType.GCP
                ).all()
                
                if not gcp_credentials:
                    logger.error(f"No GCP credentials found for user {user_id}")
                    raise ValueError("Tidak ditemukan kredensial GCP untuk pengguna ini")
                
                # Process each credential
                for cred in gcp_credentials:
                    try:
                        # Run sync for each credential
                        result = self.sync_gcp_vms(user_id, cred.id)
                        
                        # Accumulate results
                        updated_count += result.get("updated_count", 0)
                        deleted_count += result.get("deleted_count", 0)
                        created_count += result.get("created_count", 0)
                        
                    except Exception as e:
                        logger.error(f"Error syncing with credential ID {cred.id}: {str(e)}")
                        # Continue to next credential
                        continue
                        
                end_time = time.time()
                logger.info(f"GCP VM synchronization completed in {end_time - start_time:.2f} seconds")
                return {
                    "status": "success",
                    "updated_count": updated_count,
                    "deleted_count": deleted_count,
                    "created_count": created_count
                }
            
            # Process specific credential
            logger.info(f"Syncing GCP VMs for user {user_id} with credential {credential_id}")
            
            try:
                # Get and validate credentials
                credential_service = CredentialService(self.db)
                
                # Check if credential exists
                cred = self.db.query(Credential).filter(
                    Credential.id == credential_id,
                    Credential.user_id == user_id,
                    Credential.type == CredentialType.GCP
                ).first()
                
                if not cred:
                    logger.error(f"GCP credential with ID {credential_id} not found for user {user_id}")
                    raise ValueError(f"Kredensial GCP dengan ID {credential_id} tidak ditemukan")
                
                # Get decrypted credentials
                credentials = credential_service.get_decrypted_credential(credential_id, user_id)
                
                # Process credential format
                if 'gcp_credentials' not in credentials:
                    credentials = {'gcp_credentials': credentials}
                    
                if not credentials['gcp_credentials']:
                    logger.error("No valid GCP credentials found")
                    raise ValueError("Kredensial GCP tidak valid atau kosong")
                    
                # Get GCP manager
                gcp_manager = self._get_gcp_manager(credentials['gcp_credentials'])
                logger.info("Created GCP manager instance")
                
                # Get instances from a targeted set of zones
                instances = []
                zones_to_check = [
                    "asia-southeast1-b",  # Singapore
                    "asia-southeast1-a",  # Singapore
                    "asia-southeast1-c",  # Singapore
                    "asia-east1-b",       # Taiwan
                    "asia-east1-a",       # Taiwan
                    "asia-east1-c",       # Taiwan
                    "us-central1-a",      # Iowa 
                    "us-central1-b",      # Iowa
                    "us-central1-c",      # Iowa
                    "us-east1-b",         # South Carolina
                    "us-east1-c",         # South Carolina
                    "us-east1-d"          # South Carolina
                ]
                
                # Get existing VMs to check their zones and add to zones_to_check
                existing_vms = self.list_vms(user_id, provider="gcp", credential_id=credential_id)
                
                # Add zones from existing VMs to ensure we check all zones where VMs exist
                for vm in existing_vms:
                    if vm.vm_metadata and 'zone' in vm.vm_metadata:
                        zone = vm.vm_metadata['zone']
                        if zone and zone not in zones_to_check:
                            zones_to_check.append(zone)
                
                logger.info(f"Checking {len(zones_to_check)} zones: {zones_to_check}")
                
                # Get instances from each zone
                for zone in zones_to_check:
                    try:
                        zone_instances = gcp_manager.list_instances(zone=zone)
                        instances.extend(zone_instances)
                        logger.info(f"Found {len(zone_instances)} instances in zone {zone}")
                    except Exception as e:
                        logger.error(f"Error listing instances in zone {zone}: {str(e)}")
                
                logger.info(f"Retrieved {len(instances)} instances from GCP")
                
                # If no instances found, delete all VMs for this credential
                if not instances:
                    logger.info("No GCP instances found")
                    
                    # Delete all VMs for this credential
                    deleted_count = 0
                    for vm in existing_vms:
                        logger.info(f"Deleting VM {vm.name} from database as it no longer exists in GCP")
                        self.db.delete(vm)
                        deleted_count += 1
                    
                    self.db.commit()
                    
                    end_time = time.time()
                    logger.info(f"GCP VM synchronization completed in {end_time - start_time:.2f} seconds")
                    return {
                        "status": "success",
                        "updated_count": 0,
                        "deleted_count": deleted_count,
                        "created_count": 0
                    }
                
                # Create maps for tracking VMs
                gcp_instance_map = {instance.get('id'): instance for instance in instances if instance.get('id')}
                gcp_instance_names = {instance.get('name'): instance for instance in instances if instance.get('name')}
                
                # Delete VMs that no longer exist in GCP
                deleted_count = 0
                for vm in existing_vms:
                    vm_exists = False
                    
                    # Check by instance_id first (most accurate)
                    if vm.instance_id and vm.instance_id in gcp_instance_map:
                        vm_exists = True
                        
                    # If not found by ID, check by name as fallback
                    elif vm.name in gcp_instance_names:
                        vm_exists = True
                    
                    if not vm_exists:
                        logger.info(f"Deleting VM {vm.name} (ID: {vm.instance_id}) from database as it no longer exists in GCP")
                        self.db.delete(vm)
                        deleted_count += 1
                
                # Commit deletion changes
                if deleted_count > 0:
                    self.db.commit()
                    logger.info(f"Deleted {deleted_count} VMs that no longer exist in GCP")
                
                # Process each instance
                updated_count = 0
                created_count = 0
                for instance in instances:
                    try:
                        instance_id = str(instance.get('id'))
                        name = instance.get('name', instance_id)
                        
                        # Get status and convert to internal format
                        gcp_status = instance.get('status', '')
                        status = self._map_gcp_status(gcp_status)
                        
                        # Skip terminated instances if desired
                        if status == VMStatus.TERMINATED:
                            logger.info(f"Skipping terminated instance: {name} (ID: {instance_id})")
                            continue
                        
                        # Get machine type
                        machine_type = instance.get('machineType', '')
                        if machine_type and '/' in machine_type:
                            machine_type = machine_type.split('/')[-1]
                        
                        # Get network interfaces
                        public_ip = None
                        private_ip = None
                        
                        # Check both formats for network interfaces
                        if 'networkInterfaces' in instance and instance['networkInterfaces']:
                            for nic in instance['networkInterfaces']:
                                if private_ip is None and 'networkIP' in nic:
                                    private_ip = nic['networkIP']
                                if public_ip is None and 'accessConfigs' in nic and nic['accessConfigs']:
                                    for config in nic['accessConfigs']:
                                        if 'natIP' in config:
                                            public_ip = config['natIP']
                                            break
                        
                        # Alternative format for network interfaces (some GCP API versions)
                        if 'network_interfaces' in instance and instance['network_interfaces']:
                            for nic in instance['network_interfaces']:
                                if private_ip is None and 'internal_ip' in nic:
                                    private_ip = nic['internal_ip']
                                if public_ip is None and 'external_ip' in nic:
                                    public_ip = nic['external_ip']
                        
                        # Get zone and region
                        zone = instance.get('zone', '')
                        if zone and '/' in zone:
                            zone = zone.split('/')[-1]
                        
                        # Extract region from zone
                        region = '-'.join(zone.split('-')[:-1]) if zone else ''
                        
                        # Create metadata for the VM
                        vm_metadata = {
                            'zone': zone,
                            'gcp_status': gcp_status,
                            'synced_at': datetime.utcnow().isoformat()
                        }
                        
                        # Find if VM exists by instance_id first, then by name
                        existing_vm = next((vm for vm in existing_vms if vm.instance_id == instance_id), None)
                        if not existing_vm and name:
                            existing_vm = next((vm for vm in existing_vms if vm.name == name), None)
                        
                        if existing_vm:
                            # Check if any important values have changed
                            has_changes = (
                                existing_vm.name != name or
                                existing_vm.status != status or
                                existing_vm.instance_type != machine_type or
                                existing_vm.public_ip != public_ip or
                                existing_vm.private_ip != private_ip or
                                existing_vm.region != region
                            )
                            
                            if has_changes:
                                # Update existing VM
                                existing_vm.name = name
                                existing_vm.status = status
                                existing_vm.instance_type = machine_type
                                existing_vm.public_ip = public_ip
                                existing_vm.private_ip = private_ip
                                existing_vm.region = region
                                existing_vm.vm_metadata = vm_metadata
                                existing_vm.updated_at = datetime.utcnow()
                                
                                updated_count += 1
                                logger.info(f"Updated VM {name} (ID: {instance_id}) with changes: status={status}, public_ip={public_ip}, private_ip={private_ip}")
                        else:
                            # Create new VM
                            vm = VM(
                                name=name,
                                provider=VMProvider.GCP,
                                region=region,
                                instance_id=instance_id,
                                instance_type=machine_type,
                                status=status,
                                public_ip=public_ip,
                                private_ip=private_ip,
                                credential_id=credential_id,
                                user_id=user_id,
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow(),
                                is_synced=True,
                                vm_metadata=vm_metadata
                            )
                            self.db.add(vm)
                            created_count += 1
                            logger.info(f"Created new VM {name} (ID: {instance_id})")
                    except Exception as e:
                        logger.error(f"Error processing GCP instance {instance.get('id', 'unknown')}: {str(e)}")
                        continue
                
                # Commit all changes
                if updated_count > 0 or created_count > 0:
                    self.db.commit()
                
                end_time = time.time()
                logger.info(f"GCP sync completed in {end_time - start_time:.2f} seconds: {updated_count} updated, {created_count} created, {deleted_count} deleted")
                return {
                    "status": "success",
                    "updated_count": updated_count,
                    "deleted_count": deleted_count,
                    "created_count": created_count
                }
            except Exception as e:
                logger.error(f"Error in GCP VM sync: {str(e)}")
                self.db.rollback()
                raise ValueError(f"Failed to sync GCP VMs: {str(e)}")
        except Exception as e:
            logger.error(f"Error in GCP sync: {str(e)}")
            self.db.rollback()
            raise ValueError(f"Failed to sync GCP VMs: {str(e)}")

    def _map_gcp_status(self, gcp_status: str) -> str:
        """
        Map GCP status to internal VMStatus.
        
        Args:
            gcp_status: GCP status string
            
        Returns:
            Mapped internal VM status
        """
        gcp_status = gcp_status.upper()
        
        if gcp_status == 'RUNNING':
            return VMStatus.RUNNING
        elif gcp_status in ['TERMINATED', 'STOPPED']:
            return VMStatus.STOPPED
        elif gcp_status == 'SUSPENDED':
            return VMStatus.STOPPED
        elif gcp_status == 'PROVISIONING' or gcp_status == 'STAGING':
            return VMStatus.CREATING
        elif gcp_status == 'REPAIRING':
            return VMStatus.REPAIRING
        else:
            return VMStatus.UNKNOWN

    def sync_aws_vms(self, user_id: int, credential_id: int):
        """
        Sync VMs from AWS to database.
        
        Args:
            user_id: User ID
            credential_id: AWS credential ID
            
        Returns:
            Dict containing sync results
        """
        logger.info(f"Syncing AWS VMs for user {user_id} with credential {credential_id}")
        
        try:
            # Get credentials
            credentials = self._get_credential(credential_id, user_id)
            if not credentials or credentials.get('type') != CredentialType.AWS:
                raise ValueError("Invalid AWS credentials")

            # Log credential details (without sensitive info)
            logger.info(f"Using AWS region: {credentials.get('aws_region', 'us-east-1')}")
            if credentials.get('aws_access_key_id'):
                logger.info(f"Access key ID ends with: ...{credentials.get('aws_access_key_id')[-4:]}")

            # Get AWS manager instance
            aws_manager = self._get_aws_manager(credentials)
            logger.info("Created AWS manager instance")

            # Get instances using the manager
            aws_instances = aws_manager.list_instances()
            logger.info(f"Retrieved {len(aws_instances)} instances from AWS")

            if not aws_instances:
                logger.info("No AWS instances found")
                return {
                    "synced_count": 0,
                    "deleted_count": 0,
                    "created_count": 0
                }

            # Get current AWS instance IDs
            current_instance_ids = {instance.get('instance_id') for instance in aws_instances if instance.get('instance_id')}
            
            # Get existing VMs from database
            existing_vms = self.list_vms(user_id, provider="aws", credential_id=credential_id)
            
            # Map nama instance -> instance untuk tracking VM yang masih ada di AWS
            aws_instance_names = {instance.get('name'): instance for instance in aws_instances}
            
            # Hapus VM yang tidak ada lagi di AWS
            deleted_count = 0
            for vm in existing_vms:
                if vm.name not in aws_instance_names:
                    logger.info(f"Deleting VM {vm.name} from database as it no longer exists in AWS")
                    self.db.delete(vm)
                    deleted_count += 1
                
            self.db.commit()
            
            # Proses setiap instance
            synced_count = 0
            created_count = 0
            for instance in aws_instances:
                try:
                    instance_id = instance.get('instance_id')
                    if not instance_id:
                        continue

                    name = instance.get('name', instance_id)
                    state = instance.get('state', '').lower()
                    
                    # Map AWS states to our VM states
                    state_map = {
                        'pending': VMStatus.CREATING,
                        'running': VMStatus.RUNNING,
                        'shutting-down': VMStatus.STOPPING,
                        'terminated': VMStatus.TERMINATED,
                        'stopping': VMStatus.STOPPING,
                        'stopped': VMStatus.STOPPED
                    }
                    status = state_map.get(state, VMStatus.UNKNOWN)
                    logger.info(f"Processing instance {instance_id} - Name: {name} - State: {state} -> {status}")

                    # Skip terminated instances
                    if status == VMStatus.TERMINATED:
                        logger.info(f"Skipping terminated instance: {instance_id}")
                        continue

                    existing_vm = next((vm for vm in existing_vms if vm.instance_id == instance_id), None)

                    if existing_vm:
                        # Update existing VM
                        existing_vm.name = name
                        existing_vm.status = status
                        existing_vm.public_ip = instance.get('public_ip')
                        existing_vm.private_ip = instance.get('private_ip')
                        existing_vm.instance_type = instance.get('instance_type')
                        synced_count += 1
                        logger.info(f"Updated existing VM: {instance_id}")
                    else:
                        # Create new VM record
                        vm = VM(
                            name=name,
                            provider=VMProvider.AWS,
                            region=aws_manager.region,  # Use region from manager
                            instance_id=instance_id,
                            instance_type=instance.get('instance_type'),
                            status=status,
                            public_ip=instance.get('public_ip'),
                            private_ip=instance.get('private_ip'),
                            credential_id=credential_id,
                            user_id=user_id
                        )
                        self.db.add(vm)
                        created_count += 1
                        logger.info(f"Created new VM: {instance_id}")

                except Exception as e:
                    logger.error(f"Error processing AWS instance {instance.get('instance_id', 'unknown')}: {str(e)}")
                    continue

            # Find and delete VMs that no longer exist in AWS
            for vm in existing_vms:
                if vm.instance_id not in current_instance_ids:
                    logger.info(f"Deleting VM that no longer exists in AWS: {vm.instance_id}")
                    self.db.delete(vm)
                    deleted_count += 1

            # Commit all changes
            self.db.commit()

            logger.info(f"AWS sync completed: {synced_count} synced, {created_count} created, {deleted_count} deleted")
            return {
                "synced_count": synced_count + created_count,  # Total number of VMs processed
                "deleted_count": deleted_count,
                "created_count": created_count
            }

        except Exception as e:
            logger.error(f"Error during AWS sync operations: {str(e)}")
            self.db.rollback()
            raise ValueError(f"Failed to sync AWS VMs: {str(e)}")

    def sync_vms_with_provider(self, user_id: int, credential_id: Optional[int] = None):
        """
        Sync VMs with cloud provider (AWS or GCP)
        
        Args:
            user_id: User ID
            credential_id: Optional credential ID to sync specific credential
            
        Returns:
            Dictionary with sync results
        """
        results = {
            "aws": {"synced": 0, "errors": []},
            "gcp": {"synced": 0, "errors": []}
        }

        try:
            # Get credentials to sync
            query = self.db.query(Credential).filter(Credential.user_id == user_id)
            if credential_id:
                query = query.filter(Credential.id == credential_id)
            credentials = query.all()

            for cred in credentials:
                try:
                    if cred.type == CredentialType.AWS:
                        result = self.sync_aws_vms(user_id, cred.id)
                        if result:
                            results["aws"]["synced"] += result.get("synced_count", 0)
                    elif cred.type == CredentialType.GCP:
                        result = self.sync_gcp_vms(user_id, cred.id)
                        if result:
                            results["gcp"]["synced"] += result.get("synced_count", 0)
                except Exception as e:
                    error_msg = f"Error syncing {cred.type.value.lower()} credential {cred.id}: {str(e)}"
                    logger.error(error_msg)
                    results[cred.type.value.lower()]["errors"].append(error_msg)

            return results

        except Exception as e:
            logger.error(f"Error in sync_vms_with_provider: {str(e)}")
            raise

    def _deploy_vm(self, vm_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Deploy VM ke cloud provider"""
        logger.info(f"Starting VM deployment for VM ID: {vm_id}, User ID: {user_id}")
        
        vm = self.get_vm(vm_id=vm_id, user_id=user_id)
        if not vm:
            logger.error(f"VM with ID {vm_id} not found for user {user_id}")
            return None
            
        # Normalize provider
        provider = normalize_provider(vm.provider)
        
        # Dapatkan kredensial
        credential_service = CredentialService(self.db)
        credential = credential_service.get_credential(
            credential_id=vm.credential_id, 
            user_id=user_id
        )
        
        if not credential:
            logger.error(f"Credential with ID {vm.credential_id} not found")
            return None
            
        # Deploy berdasarkan provider
        if provider == "aws":
            return self._deploy_aws_vm(vm, credential)
        elif provider == "gcp":
            return self._deploy_gcp_vm(vm, credential)
        else:
            logger.error(f"Unsupported provider: {provider}")
            return None 

    def generate_ssh_key_pair(self, vm_id: int, user_id: int) -> dict:
        """Generate a new SSH key pair for a VM"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Generate public key
        public_key = private_key.public_key()

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Serialize public key
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        )

        # Store keys in VM metadata
        vm = self.get_vm(vm_id=vm_id, user_id=user_id)
        if not vm:
            raise ValueError("VM not found")

        vm_metadata = vm.vm_metadata or {}
        vm_metadata.update({
            "ssh_public_key": public_pem.decode(),
            "ssh_private_key": private_pem.decode(),
            "ssh_user": "ubuntu"  # Default user, adjust based on VM image
        })

        # Update VM metadata
        self.db.query(VM).filter(
            VM.id == vm_id,
            VM.user_id == user_id
        ).update({"vm_metadata": vm_metadata})
        
        self.db.commit()

        return {
            "public_key": public_pem.decode(),
            "private_key": private_pem.decode()
        }

    def get_ssh_key(self, vm_id: int, user_id: int) -> str:
        """Get SSH private key for a VM"""
        vm = self.get_vm(vm_id=vm_id, user_id=user_id)
        if not vm or not vm.vm_metadata:
            raise ValueError("VM or SSH key not found")

        private_key = vm.vm_metadata.get("ssh_private_key")
        if not private_key:
            # Generate new key pair if not exists
            keys = self.generate_ssh_key_pair(vm_id, user_id)
            private_key = keys["private_key"]

        return private_key

    def _update_vm_metadata(self, vm: VM, vm_data: Dict[str, Any]):
        """
        Update metadata VM setelah deployment
        
        Args:
            vm: Instance VM
            vm_data: Data VM
        """
        try:
            # Inisialisasi metadata jika kosong
            if not vm.vm_metadata:
                vm.vm_metadata = {}
            
            # Update metadata berdasarkan provider
            if vm.provider == VMProvider.GCP:
                # Untuk GCP, tambahkan zone
                zone = vm_data.get('zone', f"{vm_data['region']}-a")
                vm.vm_metadata["zone"] = zone
            
            # Tambahkan username SSH default
            if "ssh_username" not in vm.vm_metadata:
                # Set default username berdasarkan provider dan image
                if vm.provider == VMProvider.AWS:
                    # AWS AMIs biasanya menggunakan 'ec2-user' atau 'ubuntu'
                    image = vm_data.get('ami_id', '').lower()
                    if 'ubuntu' in image:
                        vm.vm_metadata["ssh_username"] = "ubuntu"
                    else:
                        vm.vm_metadata["ssh_username"] = "ec2-user"
                elif vm.provider == VMProvider.GCP:
                    # GCP instances biasanya menggunakan nama user dari image
                    image = vm_data.get('image', '').lower()
                    if 'ubuntu' in image:
                        vm.vm_metadata["ssh_username"] = "ubuntu"
                    else:
                        vm.vm_metadata["ssh_username"] = "debian"  # Default untuk Debian images
            
            self.db.commit()
            logger.info(f"Successfully updated VM {vm.id} metadata: {vm.vm_metadata}")
            
        except Exception as e:
            logger.error(f"Error updating VM metadata: {str(e)}")
            # Tidak raise exception karena ini non-critical operation