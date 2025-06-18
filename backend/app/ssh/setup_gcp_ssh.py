"""
Script to set up SSH access to a GCP VM.
This script generates an SSH key pair and adds it to the GCP VM's metadata.
"""

import os
import argparse
import base64
import json
import logging
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from google.cloud import compute_v1
from google.oauth2 import service_account
from google.cloud.compute_v1.types import Metadata, Items  # penting!

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_ssh_key_pair(output_dir=None):
    """
    Generate a new SSH key pair
    
    Args:
        output_dir: Directory to save the key files
        
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
    
    # Save keys to files if output_dir is provided
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        private_key_path = os.path.join(output_dir, "id_rsa")
        public_key_path = os.path.join(output_dir, "id_rsa.pub")
        
        with open(private_key_path, "w") as f:
            f.write(private_key_pem)
        
        with open(public_key_path, "w") as f:
            f.write(public_key)
        
        # Set correct permissions for private key
        os.chmod(private_key_path, 0o600)
        
        logger.info(f"SSH keys saved to {private_key_path} and {public_key_path}")
    
    return private_key_pem, public_key

def add_ssh_key_to_instance(credentials_json, project_id, instance_name, zone, username, public_key):
    """
    Add SSH key to GCP instance metadata
    """
    try:
        if os.path.isfile(credentials_json):
            with open(credentials_json, 'r') as f:
                credentials_data = json.load(f)
        else:
            credentials_data = json.loads(credentials_json)

        credentials = service_account.Credentials.from_service_account_info(credentials_data)
        instance_client = compute_v1.InstancesClient(credentials=credentials)

        ssh_key_entry = f"{username}:{public_key}"

        instance = instance_client.get(
            project=project_id,
            zone=zone,
            instance=instance_name
        )

        metadata = instance.metadata or Metadata()
        fingerprint = metadata.fingerprint
        existing_ssh_keys = ""

        if metadata.items:
            for item in metadata.items:
                if item.key == "ssh-keys":
                    existing_ssh_keys = item.value
                    break

        combined_ssh_keys = (
            f"{existing_ssh_keys}\n{ssh_key_entry}" if existing_ssh_keys else ssh_key_entry
        )

        ssh_item = Items(key="ssh-keys", value=combined_ssh_keys)
        metadata.items = [ssh_item]
        metadata.fingerprint = fingerprint

        operation = instance_client.set_metadata(
            project=project_id,
            zone=zone,
            instance=instance_name,
            metadata=metadata
        )

        operation.result(timeout=60)
        logger.info(f"Added SSH key for user {username} to instance {instance_name}")
        return True

    except Exception as e:
        logger.error(f"Error adding SSH key to instance {instance_name}: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Set up SSH access to a GCP VM")
    parser.add_argument("--credentials", required=True, help="Path to GCP credentials JSON file")
    parser.add_argument("--project-id", required=True, help="GCP project ID")
    parser.add_argument("--instance-name", required=True, help="Name of the GCP instance")
    parser.add_argument("--zone", required=True, help="Zone where the instance is located")
    parser.add_argument("--username", default="cloud-user", help="Username for SSH access")
    parser.add_argument("--output-dir", default=".", help="Directory to save the key files")
    
    args = parser.parse_args()
    
    # Generate SSH key pair
    private_key, public_key = generate_ssh_key_pair(args.output_dir)
    
    # Add SSH key to instance
    success = add_ssh_key_to_instance(
        args.credentials,
        args.project_id,
        args.instance_name,
        args.zone,
        args.username,
        public_key
    )
    
    if success:
        print(f"SSH access set up successfully for {args.username}@{args.instance_name}")
        print(f"To connect, use: ssh -i {os.path.join(args.output_dir, 'id_rsa')} {args.username}@<VM_IP_ADDRESS>")
    else:
        print("Failed to set up SSH access")

if __name__ == "__main__":
    main()
