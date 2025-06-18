import os
import base64
import logging
import subprocess
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from google.cloud import compute_v1
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class GcpSshHelper:
    """Helper class for managing SSH keys for GCP VMs"""
    
    def __init__(self, credentials):
        """
        Initialize GCP SSH Helper
        
        Args:
            credentials: Dictionary containing GCP credentials
        """
        # Log struktur kredensial untuk debugging
        logger.info(f"Credentials keys: {list(credentials.keys()) if credentials else 'None'}")
        
        # Periksa apakah kredensial memiliki struktur yang diharapkan
        if 'gcp_credentials' in credentials:
            # Struktur baru: credentials['gcp_credentials']['gcp_project_id']
            gcp_creds = credentials['gcp_credentials']
            logger.info(f"Using nested gcp_credentials structure: {list(gcp_creds.keys())}")
            self.project_id = gcp_creds.get('gcp_project_id')
            self.service_account_info = gcp_creds.get('gcp_service_account_json')
        else:
            # Struktur lama: credentials['gcp_project_id']
            logger.info("Using flat credentials structure")
            self.project_id = credentials.get('gcp_project_id')
            self.service_account_info = credentials.get('gcp_service_account_json')
        
        # Validasi bahwa informasi yang diperlukan ada
        if not self.project_id:
            logger.error("Missing GCP project_id in credentials")
            raise ValueError("Missing GCP project_id in credentials")
            
        if not self.service_account_info:
            logger.error("Missing GCP service_account_json in credentials")
            raise ValueError("Missing GCP service_account_json in credentials")
        
        # Create GCP credentials
        self.credentials = service_account.Credentials.from_service_account_info(
            self.service_account_info
        )
        
        # Initialize GCP client
        self.instance_client = compute_v1.InstancesClient(credentials=self.credentials)
    
    def generate_ssh_key_pair(self):
        """
        Generate a new SSH key pair
        
        Returns:
            Tuple of (private_key, public_key)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Get private key in PEM format
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')
        
        # Get public key in OpenSSH format
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH
        ).decode('utf-8')
        
        return private_key_pem, public_key
    
    def add_ssh_key_to_instance(self, instance_name, zone, username, public_key):
        """
        Add SSH key to GCP instance metadata.

        Args:
            instance_name: Name of the instance
            zone: Zone where the instance is located
            username: Username for SSH access
            public_key: Public key in OpenSSH format

        Returns:
            True if successful, False otherwise
        """
        try:
            # Format SSH key entry
            ssh_key_entry = f"{username}:{public_key}"

            # Get current instance
            instance = self.instance_client.get(
                project=self.project_id,
                zone=zone,
                instance=instance_name
            )

            # Extract existing ssh-keys
            existing_ssh_keys = ""
            if instance.metadata and instance.metadata.items:
                for item in instance.metadata.items:
                    if item.key == "ssh-keys":
                        existing_ssh_keys = item.value
                        break

            # Combine with new key
            combined_ssh_keys = (
                f"{existing_ssh_keys}\n{ssh_key_entry}" if existing_ssh_keys else ssh_key_entry
            )

            # Create metadata update request
            metadata_body = compute_v1.Metadata()
            metadata_body.fingerprint = instance.metadata.fingerprint
            
            # Create items list for metadata
            items = []
            
            # Add the ssh-keys item
            ssh_item = compute_v1.Items()
            ssh_item.key = "ssh-keys"
            ssh_item.value = combined_ssh_keys
            items.append(ssh_item)
            
            # Add any existing items that aren't ssh-keys to preserve them
            if instance.metadata and instance.metadata.items:
                for item in instance.metadata.items:
                    if item.key != "ssh-keys":
                        items.append(item)
            
            # Set the items in the metadata
            metadata_body.items = items

            # Update metadata on instance
            logger.info(f"Updating metadata for instance {instance_name} with new SSH key")
            operation = self.instance_client.set_metadata(
                project=self.project_id,
                zone=zone,
                instance=instance_name,
                metadata_resource=metadata_body  # Use metadata_resource parameter name
            )

            operation.result(timeout=60)
            logger.info(f"Added SSH key for user {username} to instance {instance_name}")
            return True

        except Exception as e:
            logger.error(f"Error adding SSH key to instance {instance_name}: {str(e)}")
            return False

    
    def setup_ssh_access(self, instance_name, zone):
        """
        Set up SSH access to a GCP instance
        
        Args:
            instance_name: Name of the instance
            zone: Zone where the instance is located
            
        Returns:
            Dictionary with SSH connection details
        """
        try:
            # Generate a new SSH key pair
            private_key, public_key = self.generate_ssh_key_pair()
            
            # Use 'cloud-user' as the username (common for GCP VMs)
            username = "cloud-user"
            
            # Add the SSH key to the instance
            success = self.add_ssh_key_to_instance(
                instance_name=instance_name,
                zone=zone,
                username=username,
                public_key=public_key
            )
            
            if not success:
                return None
            
            # Return SSH connection details
            return {
                "username": username,
                "private_key": private_key,
                "public_key": public_key
            }
            
        except Exception as e:
            logger.error(f"Error setting up SSH access for instance {instance_name}: {str(e)}")
            return None