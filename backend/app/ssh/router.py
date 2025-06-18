import asyncio
import asyncssh
import logging
import json
from typing import Dict, Optional, Any
from fastapi import APIRouter, WebSocket, HTTPException, status, Query
from tempfile import NamedTemporaryFile
import os
from app.auth.jwt import verify_token_ws
from app.database import SessionLocal
from app.users.models import User
from app.vm.models import VM, VMProvider
from app.credentials.service import CredentialService
from app.ssh.gcp_ssh_helper import GcpSshHelper
from app.ssh.gcp_oslogin_helper import GcpOsLoginHelper
from app.ssh.aws_ssh_helper import AwsSshHelper
from app.ssh.ssh_control import ssh_control

logger = logging.getLogger(__name__)

router = APIRouter()

class SSHManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.active_connections = {}
        return cls._instance

    def __init__(self):
        self.active_connections: Dict[str, asyncssh.SSHClientConnection] = {}
        
    async def connect(
        self,
        hostname: str,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        port: int = 22
    ) -> asyncssh.SSHClientConnection:
        """Create SSH connection to remote host"""
        try:
            # Create temporary file for private key if provided
            key_file = None
            try:
                if private_key:
                    key_file = NamedTemporaryFile(delete=False, mode='w')
                    key_file.write(private_key)
                    key_file.close()
                    
                conn = await asyncssh.connect(
                    hostname,
                    username=username,
                    password=password,
                    client_keys=[key_file.name] if key_file else None,
                    known_hosts=None,  # In production, handle known_hosts properly
                    port=port
                )
            finally:
                # Clean up temporary key file
                if key_file:
                    os.unlink(key_file.name)
            return conn
        except Exception as e:
            logger.error(f"SSH connection failed: {str(e)}")
            raise

    async def create_session(
        self,
        conn: asyncssh.SSHClientConnection,
        term_type: str = "xterm-256color",
        width: int = 80,
        height: int = 24
    ) -> asyncssh.SSHClientSession:
        """Create interactive shell session"""
        try:
            session = await conn.create_session(
                term_type=term_type,
                term_size=(width, height)
            )
            return session
        except Exception as e:
            logger.error(f"Failed to create SSH session: {str(e)}")
            raise

    async def handle_websocket(
        self,
        websocket: WebSocket,
        hostname: str,
        username: str,
        password: Optional[str] = None,
        private_key: Optional[str] = None,
        port: int = 22
    ):
        """Handle WebSocket connection and bridge it to SSH"""
        try:
            # Create SSH connection
            conn = await self.connect(
                hostname=hostname,
                username=username,
                password=password,
                private_key=private_key,
                port=port
            )
            
            # Wait for initial terminal size
            try:
                size_data = await websocket.receive_json()
                term_width = size_data.get("cols", 80)
                term_height = size_data.get("rows", 24)
            except Exception:
                term_width, term_height = 80, 24
            
            # Create interactive shell with size
            async with conn.create_process(
                term_type="xterm-256color",
                term_size=(term_width, term_height)
            ) as process:
                # Handle I/O between WebSocket and SSH
                await self._handle_ssh_io(websocket, process)
                
        except Exception as e:
            logger.error(f"SSH connection error: {str(e)}")
            try:
                if websocket.application_state != websocket.ApplicationState.DISCONNECTED:
                    await websocket.send_text(f"\r\nConnection error: {str(e)}")
                    await websocket.close()
            except Exception as close_error:
                logger.error(f"Error when closing websocket: {str(close_error)}")
        finally:
            # Clean up
            if 'conn' in locals():
                conn.close()
                await conn.wait_closed()
    
    async def _handle_ssh_io(self, websocket: WebSocket, process):
        """Handle bidirectional I/O between WebSocket and SSH process"""

        # Forward SSH output to WebSocket
        async def reader():
            try:
                while True:
                    data = await process.stdout.read(1024)
                    if not data:
                        break

                    # Pastikan konversi dari bytes ke str aman
                    text = data.decode('utf-8', errors='ignore') if isinstance(data, bytes) else str(data)
                    await websocket.send_text(text)
            except Exception as e:
                logger.error(f"SSH reader error: {str(e)}")

        # Forward WebSocket input to SSH
        async def writer():
            try:
                while True:
                    try:
                        message = await websocket.receive_json()
                    except Exception as e:
                        logger.warning(f"WebSocket message not valid JSON: {str(e)}")
                        try:
                            # Coba terima sebagai text biasa
                            raw = await websocket.receive_text()
                            logger.debug(f"Received raw text: {repr(raw)}")
                            process.stdin.write(raw)
                            await process.stdin.drain()
                            continue
                        except Exception as e2:
                            logger.error(f"Error handling raw WebSocket input: {str(e2)}")
                            break

                    # Handle terminal resize
                    if message.get('type') == 'resize':
                        process.change_terminal_size(
                            width=message.get('cols', 80),
                            height=message.get('rows', 24)
                        )
                        
                        continue   

                    # Handle terminal input
                    if message.get('type') == 'input' and 'data' in message:
                        data = message['data']
                        try:
                            if not isinstance(data, str):
                                data = str(data)
                            process.stdin.write(data)
                            await process.stdin.drain()
                        except Exception as e:
                            logger.error(f"Error writing to SSH stdin: {str(e)}")
            except Exception as e:
                logger.error(f"WebSocket writer error: {str(e)}")

        try:
            # Jalankan reader dan writer secara paralel
            reader_task = asyncio.create_task(reader())
            writer_task = asyncio.create_task(writer())

            # Tunggu salah satu selesai
            done, pending = await asyncio.wait(
                [reader_task, writer_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Batalkan yang masih berjalan
            for task in pending:
                task.cancel()
        except Exception as e:
            logger.error(f"Error in SSH I/O handling: {str(e)}")


# Create a singleton instance
ssh_manager = SSHManager()

@router.websocket("/ws/ssh/{vm_id}")
async def ssh_endpoint(
    websocket: WebSocket,
    vm_id: int,
    token: str = Query(...)
):
    try:
        # Verify token
        payload = verify_token_ws(token)
        if not payload:
            logger.error("Invalid token in WebSocket connection")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        # Get user email from token
        email = payload.get("sub")
        
        # Get user and VM details
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                logger.error(f"User not found for email: {email}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            vm = db.query(VM).filter(VM.id == vm_id).first()
            if not vm:
                logger.error(f"VM not found with id: {vm_id}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Check if user has access to this VM
            if vm.user_id != user.id:
                logger.error(f"User {user.id} does not have access to VM {vm_id}")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            # Accept the WebSocket connection
            await websocket.accept()
            
            # Use public_ip if available, otherwise use private_ip
            ip_to_use = vm.public_ip or vm.private_ip
            if not ip_to_use:
                logger.error(f"VM {vm_id} has no IP address configured")
                await websocket.send_text("Error: VM has no IP address configured. Please make sure the VM is running and has a valid IP address.")
                await websocket.close()
                return
                
            logger.info(f"Connecting to VM {vm_id} at {ip_to_use}")
            
            # Handle SSH credentials based on VM provider
            ssh_username = "root"  # Default SSH username
            ssh_password = None    # Default to no password
            ssh_private_key = None # Default to no private key
            ssh_port = 22         # Default SSH port
            
            # Try to get SSH credentials from VM metadata if available
            if vm.vm_metadata:
                ssh_username = vm.vm_metadata.get('ssh_username', ssh_username)
                # Only use password from metadata if it exists
                if 'ssh_password' in vm.vm_metadata:
                    ssh_password = vm.vm_metadata.get('ssh_password')
                # Only use private key from metadata if it exists
                if 'ssh_private_key' in vm.vm_metadata:
                    ssh_private_key = vm.vm_metadata.get('ssh_private_key')
                # Get SSH port if specified
                if 'ssh_port' in vm.vm_metadata:
                    ssh_port = vm.vm_metadata.get('ssh_port', ssh_port)
                    
            # For cloud VMs, we need to set up SSH keys if they don't exist
            if not ssh_private_key:
                logger.info(f"Setting up SSH keys for {vm.provider} VM {vm.id}")
                try:
                    # Get the credential service
                    credential_service = CredentialService(db)
                    
                    # Get the VM's credential
                    credentials = credential_service.get_decrypted_credential(vm.credential_id, user.id)
                    
                    if not credentials:
                        logger.error(f"Could not get credentials for VM {vm.id}")
                        await websocket.send_text("Error: Could not get credentials for this VM.")
                        await websocket.close()
                        return
                    
                    # Get region and zone from VM metadata
                    region = vm.region
                    zone = None
                    instance_id = vm.instance_id or vm.name
                    
                    if vm.vm_metadata:
                        if 'zone' in vm.vm_metadata:
                            zone = vm.vm_metadata['zone']
                        if 'instance_id' in vm.vm_metadata:
                            instance_id = vm.vm_metadata['instance_id']
                    
                    # For GCP VMs, zone is required
                    if vm.provider == VMProvider.GCP and not zone:
                        logger.error(f"Zone information missing for GCP VM {vm.id}")
                        await websocket.send_text("Error: Zone information missing for this GCP VM.")
                        await websocket.close()
                        return
                    
                    # Set up SSH access using the SSH control module
                    await websocket.send_text(f"Setting up SSH access for {vm.provider} VM {vm.id}...\r\n")
                    
                    try:
                        # Use the SSH control to set up access
                        ssh_info = ssh_control.setup_ssh_access(
                            provider=vm.provider,
                            credentials=credentials,
                            instance_id=instance_id,
                            region=region,
                            zone=zone
                        )
                        
                        if not ssh_info:
                            logger.error(f"Failed to set up SSH access for {vm.provider} VM {vm.id}")
                            await websocket.send_text(f"Error: Failed to set up SSH access for this {vm.provider} VM.")
                            await websocket.close()
                            return
                        
                        # Use the SSH info
                        ssh_username = ssh_info["username"]
                        ssh_private_key = ssh_info["private_key"]
                        
                        # Update VM metadata with SSH info
                        if not vm.vm_metadata:
                            vm.vm_metadata = {}
                        
                        vm.vm_metadata["ssh_username"] = ssh_username
                        vm.vm_metadata["ssh_private_key"] = ssh_private_key
                        
                        # Save the updated VM
                        db.commit()
                        
                        logger.info(f"SSH access set up for {vm.provider} VM {vm.id} with username {ssh_username}")
                        
                    except Exception as e:
                        logger.error(f"Error setting up SSH for {vm.provider} VM {vm.id}: {str(e)}")
                        await websocket.send_text(f"Error setting up SSH: {str(e)}")
                        await websocket.close()
                        return
                    
                except Exception as e:
                    logger.error(f"Error setting up SSH for {vm.provider} VM {vm.id}: {str(e)}")
                    await websocket.send_text(f"Error setting up SSH: {str(e)}")
                    await websocket.close()
                    return
            
            logger.info(f"Using SSH username: {ssh_username} for VM {vm_id}")
            
            # Handle SSH connection
            await ssh_manager.handle_websocket(
                websocket=websocket,
                hostname=ip_to_use,
                username=ssh_username,
                password=ssh_password,
                private_key=ssh_private_key,
                port=ssh_port
            )
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in SSH endpoint: {str(e)}")
        try:
            # Check if the websocket is still connected before trying to close it
            if websocket.application_state != websocket.ApplicationState.DISCONNECTED:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception as close_error:
            # Websocket might already be closed
            logger.error(f"Error closing websocket: {str(close_error)}")
            pass