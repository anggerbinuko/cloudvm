"""
SSH Control module for managing SSH connections to cloud VMs across different providers.
This module serves as a central control point for SSH connections and provides a unified interface
for setting up SSH access to VMs from different cloud providers.
"""
import logging
from enum import Enum
from typing import Dict, Optional, Any, Union

from app.vm.models import VMProvider
from app.ssh.gcp_ssh_helper import GcpSshHelper
from app.ssh.gcp_oslogin_helper import GcpOsLoginHelper
from app.ssh.aws_ssh_helper import AwsSshHelper

logger = logging.getLogger(__name__)

class SshSetupStrategy(Enum):
    """Enum defining different SSH setup strategies"""
    DEFAULT = "default"
    GCP_METADATA = "gcp_metadata"
    GCP_OSLOGIN = "gcp_oslogin"
    AWS_KEYPAIR = "aws_keypair"
    PASSWORD = "password"

class SshControl:
    """
    Central control class for managing SSH connections to cloud VMs.
    This class provides a unified interface for setting up SSH access to VMs
    from different cloud providers.
    """
    
    def __init__(self):
        """Initialize SSH Control"""
        self.helpers = {}
    
    def get_helper(self, provider: Union[str, VMProvider], credentials: Dict[str, Any]) -> Any:
        """Get or create an appropriate SSH helper for the given provider"""
        
        if isinstance(provider, str):
            provider = provider.lower()
            provider_enum = VMProvider(provider)
        else:
            provider_enum = provider
            provider = provider_enum.value.lower()
        
        logger.info(f"Getting helper for provider: {provider}")
        
        helper_key = provider

        if helper_key in self.helpers:
            return self.helpers[helper_key]

        if provider == "gcp":
            gcp_ssh_helper = GcpSshHelper(credentials)
            gcp_oslogin_helper = GcpOsLoginHelper(credentials)
            self.helpers["gcp_metadata"] = gcp_ssh_helper
            self.helpers["gcp_oslogin"] = gcp_oslogin_helper
            return {
                "metadata": gcp_ssh_helper,
                "oslogin": gcp_oslogin_helper
            }
        elif provider == "aws":
            from app.ssh.aws_ssh_helper import AwsSshHelper
            aws_ssh_helper = AwsSshHelper(credentials)
            self.helpers["aws"] = aws_ssh_helper
            return aws_ssh_helper
        else:
            logger.error(f"Unsupported provider: {provider}")
            raise ValueError(f"Unsupported provider: {provider}")

    def setup_ssh_access(
    self,
    provider: str,
    credentials: Dict[str, Any],
    instance_id: str,
    region: str,
    zone: Optional[str] = None,
    strategy: Optional[SshSetupStrategy] = None
) -> Optional[Dict[str, str]]:
        """
        Set up SSH access to a cloud VM
        
        Args:
            provider: Cloud provider (e.g., 'GCP', 'AWS')
            credentials: Dictionary containing provider credentials
            instance_id: Instance ID or name
            region: Region where the instance is located
            zone: Zone where the instance is located (required for GCP)
            strategy: SSH setup strategy to use (optional)
            
        Returns:
            Dictionary with SSH connection details if successful, None otherwise
        """
        # Convert provider to string if it's an enum
        if hasattr(provider, 'value'):
            provider = provider.value
        else:
            provider = str(provider).lower()
            
        logger.info(f"Setting up SSH access for {provider} instance {instance_id} in {region}")
        
        # Determine the strategy if not provided
        if not strategy:
            if provider == VMProvider.GCP.value:
                strategy = SshSetupStrategy.GCP_OSLOGIN
            elif provider == VMProvider.AWS.value:
                strategy = SshSetupStrategy.AWS_KEYPAIR
            else:
                strategy = SshSetupStrategy.DEFAULT
        
        try:
            # Handle GCP VMs - UNCHANGED FROM ORIGINAL
            if provider == VMProvider.GCP.value:
                if not zone:
                    logger.error(f"Zone is required for GCP instances")
                    return None
                
                helpers = self.get_helper(provider, credentials)
                
                # Try OS Login first if that's the strategy
                if strategy == SshSetupStrategy.GCP_OSLOGIN:
                    try:
                        logger.info(f"Using OS Login strategy for GCP instance {instance_id}")
                        ssh_info = helpers["oslogin"].setup_ssh_access(instance_id, zone)
                        
                        if ssh_info:
                            logger.info(f"Successfully set up SSH access using OS Login for GCP instance {instance_id}")
                            return ssh_info
                        else:
                            # Fall back to metadata method if OS Login fails
                            logger.info(f"OS Login failed, falling back to metadata method for GCP instance {instance_id}")
                            strategy = SshSetupStrategy.GCP_METADATA
                    except Exception as e:
                        logger.warning(f"OS Login error: {str(e)}, falling back to metadata method")
                        strategy = SshSetupStrategy.GCP_METADATA
                
                # Use metadata method if that's the strategy or if OS Login failed
                if strategy == SshSetupStrategy.GCP_METADATA:
                    logger.info(f"Using metadata strategy for GCP instance {instance_id}")
                    ssh_info = helpers["metadata"].setup_ssh_access(instance_id, zone)
                    
                    if ssh_info:
                        logger.info(f"Successfully set up SSH access using metadata for GCP instance {instance_id}")
                        return ssh_info
                
                logger.error(f"Failed to set up SSH access for GCP instance {instance_id} using both methods")
                return None
            
            # Handle AWS EC2 instances - IMPROVED VERSION
            elif provider == VMProvider.AWS.value:
                helper = self.get_helper(provider, credentials)
                
                # Determine strategy based on instance properties
                aws_strategy = "auto"
                
                if strategy == SshSetupStrategy.AWS_KEYPAIR:
                    aws_strategy = "keypair"
                elif strategy == SshSetupStrategy.DEFAULT:
                    # If no specific strategy is requested, try multiple strategies in sequence
                    aws_strategy = "auto"
                
                logger.info(f"Using AWS SSH strategy: {aws_strategy} for instance {instance_id}")
                
                # The improved AWS helper will try multiple strategies in sequence
                ssh_info = helper.setup_ssh_access(instance_id, region, strategy=aws_strategy)
                
                if ssh_info:
                    logger.info(f"Successfully set up SSH access for AWS instance {instance_id}")
                    # Add connection type to vm_metadata for future reference
                    ssh_info['connection_type'] = ssh_info.get('connection_type', 'standard_ssh')
                    return ssh_info
                
                # If all automated methods fail, provide a diagnostic message
                logger.error(f"Failed to set up SSH access for AWS instance {instance_id}")
                logger.info("Checking instance prerequisites for SSH access...")
                
                # Check prerequisites and give better error information
                error_info = self._check_aws_ssh_prerequisites(helper, instance_id, region)
                if error_info:
                    logger.error(f"AWS SSH prerequisites check failed: {error_info}")
                
                return None
            
            # Handle other providers (not implemented yet)
            else:
                logger.error(f"SSH setup for provider {provider} is not implemented")
                return None
                
        except Exception as e:
            logger.error(f"Error setting up SSH access: {str(e)}")
            return None

    def _check_aws_ssh_prerequisites(self, helper, instance_id: str, region: str) -> Optional[str]:
        """
        Check prerequisites for AWS SSH connection and return error information
        
        Args:
            helper: AWS SSH helper instance
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            Error message string if prerequisites not met, None if all prerequisites are met
        """
        try:
            # Get instance details
            instance_details = helper._get_instance_details(instance_id, region)
            
            if not instance_details:
                return f"Instance {instance_id} not found in region {region}"
            
            # Check if instance is running
            if instance_details.get('state') != 'running':
                return f"Instance {instance_id} is not in running state (current state: {instance_details.get('state')})"
            
            # Check if instance has a public IP
            if not instance_details.get('public_ip'):
                return f"Instance {instance_id} does not have a public IP address"
            
            # Check if instance has a key pair associated
            if not instance_details.get('key_name'):
                return f"Instance {instance_id} does not have an associated key pair"
            
            # Check if SSM is enabled
            if not instance_details.get('ssm_enabled'):
                return f"SSM is not enabled for instance {instance_id}. Install SSM agent and ensure the instance has the AmazonSSMManagedInstanceCore IAM role"
            
            # All prerequisites are met
            return None
        except Exception as e:
            return f"Error checking AWS SSH prerequisites: {str(e)}"
    
    def get_ssh_connection_info(
        self,
        provider: Union[str, VMProvider],
        vm_metadata: Dict[str, Any],
        credentials: Dict[str, Any],
        instance_id: str,
        region: str,
        zone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get SSH connection information for a VM
        
        Args:
            provider: Cloud provider (e.g., 'GCP', 'AWS') or VMProvider enum
            vm_metadata: VM metadata containing SSH information
            credentials: Dictionary containing provider credentials
            instance_id: Instance ID or name
            region: Region where the instance is located
            zone: Zone where the instance is located (required for GCP)
            
        Returns:
            Dictionary with SSH connection details
        """
        # Check if SSH information already exists in metadata
        if vm_metadata and 'ssh_username' in vm_metadata and 'ssh_private_key' in vm_metadata:
            logger.info(f"Using existing SSH information from VM metadata")
            return {
                "username": vm_metadata['ssh_username'],
                "private_key": vm_metadata['ssh_private_key'],
                "port": vm_metadata.get('ssh_port', 22)
            }
        
        # Set up SSH access if not available in metadata
        logger.info(f"No SSH information in metadata, setting up SSH access")
        ssh_info = self.setup_ssh_access(provider, credentials, instance_id, region, zone)
        
        if not ssh_info:
            logger.error(f"Failed to set up SSH access")
            return {
                "username": "root",  # Default fallback
                "private_key": None,
                "port": 22
            }
        
        return {
            "username": ssh_info["username"],
            "private_key": ssh_info["private_key"],
            "port": 22
        }


# Create a singleton instance
ssh_control = SshControl()
