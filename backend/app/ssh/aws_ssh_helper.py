"""
AWS SSH Helper Module - Enhanced version with multiple connection strategies
"""
import os
import logging
import boto3
import base64
import paramiko
import time
from typing import Dict, Any, Optional, List, Tuple
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

class AwsSshHelper:
    """
    AWS SSH Helper class to manage SSH connections to EC2 instances
    with support for multiple connection strategies.
    """
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize AWS SSH Helper with AWS credentials
        
        Args:
            credentials: Dictionary containing AWS credentials
        """
        self.credentials = credentials
        # Cache for EC2 clients by region
        self.ec2_clients = {}
        # Cache for SSM clients by region
        self.ssm_clients = {}
        # Temporary key storage
        self.temp_key_dir = "/tmp/aws_ssh_keys"
        os.makedirs(self.temp_key_dir, exist_ok=True)
    
    def _get_ec2_client(self, region: str):
        """
        Get or create an EC2 client for the specified region
        
        Args:
            region: AWS region
            
        Returns:
            boto3 EC2 client
        """
        if region not in self.ec2_clients:
            self.ec2_clients[region] = boto3.client(
                'ec2',
                region_name=region,
                aws_access_key_id=self.credentials.get('aws_access_key_id'),
                aws_secret_access_key=self.credentials.get('aws_secret_access_key')
            )
        return self.ec2_clients[region]
    
    def _get_ssm_client(self, region: str):
        """
        Get or create an SSM client for the specified region
        
        Args:
            region: AWS region
            
        Returns:
            boto3 SSM client
        """
        if region not in self.ssm_clients:
            self.ssm_clients[region] = boto3.client(
                'ssm',
                region_name=region,
                aws_access_key_id=self.credentials.get('aws_access_key_id'),
                aws_secret_access_key=self.credentials.get('aws_secret_access_key')
            )
        return self.ssm_clients[region]
    
    def _get_instance_details(self, instance_id: str, region: str) -> Dict[str, Any]:
        """
        Get detailed information about an EC2 instance
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            Dictionary with instance details
        """
        try:
            ec2_client = self._get_ec2_client(region)
            response = ec2_client.describe_instances(InstanceIds=[instance_id])
            
            if not response['Reservations'] or not response['Reservations'][0]['Instances']:
                logger.error(f"Instance {instance_id} not found in region {region}")
                return {}
            
            instance = response['Reservations'][0]['Instances'][0]
            
            # Extract the AMI ID to determine the default username
            ami_id = instance.get('ImageId', '')
            platform = instance.get('Platform', '')
            
            # Extract key name
            key_name = instance.get('KeyName')
            
            # Determine if SSM is enabled
            ssm_enabled = False
            for tag in instance.get('Tags', []):
                if tag['Key'] == 'SSMEnabled' and tag['Value'].lower() == 'true':
                    ssm_enabled = True
                    break
            
            # Check if instance has a public IP
            public_ip = instance.get('PublicIpAddress')
            private_ip = instance.get('PrivateIpAddress')
            
            # Check if SSM agent is installed 
            ssm_status = self._check_ssm_status(instance_id, region)
            
            return {
                "instance_id": instance_id,
                "ami_id": ami_id,
                "platform": platform,
                "key_name": key_name,
                "public_ip": public_ip,
                "private_ip": private_ip,
                "ssm_enabled": ssm_enabled or ssm_status,
                "vpc_id": instance.get('VpcId'),
                "subnet_id": instance.get('SubnetId'),
                "state": instance.get('State', {}).get('Name')
            }
        except Exception as e:
            logger.error(f"Error getting EC2 instance details: {str(e)}")
            return {}
    
    def _check_ssm_status(self, instance_id: str, region: str) -> bool:
        """
        Check if SSM is available for the instance
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            True if SSM is available, False otherwise
        """
        try:
            ssm_client = self._get_ssm_client(region)
            response = ssm_client.describe_instance_information(
                Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}]
            )
            
            return len(response.get('InstanceInformationList', [])) > 0
        except Exception as e:
            logger.debug(f"SSM status check failed: {str(e)}")
            return False
    
    def _determine_username(self, ami_id: str, platform: str) -> str:
        """
        Determine the default SSH username based on the AMI ID and platform
        
        Args:
            ami_id: AMI ID
            platform: Platform (windows, linux, etc.)
            
        Returns:
            Default username for the instance
        """
        # Handle platform-specific usernames
        if platform == 'windows':
            return 'Administrator'
        
        # Common AMI prefixes and their default usernames
        ami_prefixes = {
            'ami-amazon-linux': 'ec2-user',  # Amazon Linux
            'ami-amazon2': 'ec2-user',      # Amazon Linux 2
            'ami-ubuntu': 'ubuntu',         # Ubuntu
            'ami-debian': 'admin',          # Debian
            'ami-rhel': 'ec2-user',         # Red Hat
            'ami-suse': 'ec2-user',         # SUSE
            'ami-centos': 'centos',         # CentOS
        }
        
        # Try to determine username by AMI ID
        try:
            ec2_client = self._get_ec2_client('us-east-1')  # Use any region for describe_images
            response = ec2_client.describe_images(ImageIds=[ami_id])
            
            if response['Images']:
                image = response['Images'][0]
                description = image.get('Description', '').lower()
                name = image.get('Name', '').lower()
                
                # Check common distro names in the description or name
                if 'amazon linux' in description or 'amazon linux' in name:
                    return 'ec2-user'
                elif 'ubuntu' in description or 'ubuntu' in name:
                    return 'ubuntu'
                elif 'debian' in description or 'debian' in name:
                    return 'admin'
                elif 'centos' in description or 'centos' in name:
                    return 'centos'
                elif 'rhel' in description or 'red hat' in name:
                    return 'ec2-user'
                elif 'suse' in description or 'suse' in name:
                    return 'ec2-user'
                elif 'fedora' in description or 'fedora' in name:
                    return 'fedora'
                elif 'bitnami' in description or 'bitnami' in name:
                    return 'bitnami'
        except Exception as e:
            logger.debug(f"Unable to determine username from AMI: {str(e)}")
        
        # Default to ec2-user if we can't determine
        return 'ec2-user'
    
    def _create_key_pair(self, instance_id: str, region: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a new key pair for the instance
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            Tuple of (key name, private key) if successful, (None, None) otherwise
        """
        key_name = f"temp-key-{instance_id}-{int(time.time())}"
        
        try:
            ec2_client = self._get_ec2_client(region)
            response = ec2_client.create_key_pair(KeyName=key_name)
            private_key = response['KeyMaterial']
            
            # Save the key to a file
            key_path = os.path.join(self.temp_key_dir, key_name)
            with open(key_path, 'w') as key_file:
                key_file.write(private_key)
            os.chmod(key_path, 0o600)
            
            return key_name, private_key
        except Exception as e:
            logger.error(f"Error creating key pair: {str(e)}")
            return None, None
    
    def _push_public_key_via_ssm(self, instance_id: str, region: str, key_name: str, private_key: str) -> bool:
        """
        Push the public key to the instance using SSM
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            key_name: Key name
            private_key: Private key content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate public key from private key
            key = paramiko.RSAKey.from_private_key_file(os.path.join(self.temp_key_dir, key_name))
            public_key = f"ssh-rsa {key.get_base64()} {key_name}"
            
            # Push the public key via SSM
            ssm_client = self._get_ssm_client(region)
            
            # Determine the default user
            instance_details = self._get_instance_details(instance_id, region)
            username = self._determine_username(
                instance_details.get('ami_id', ''),
                instance_details.get('platform', '')
            )
            
            # Command to add the key to authorized_keys
            command = f"""
            mkdir -p /home/{username}/.ssh
            echo '{public_key}' >> /home/{username}/.ssh/authorized_keys
            chmod 700 /home/{username}/.ssh
            chmod 600 /home/{username}/.ssh/authorized_keys
            chown -R {username}:{username} /home/{username}/.ssh
            """
            
            # Execute the command via SSM
            response = ssm_client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={'commands': [command]}
            )
            
            command_id = response['Command']['CommandId']
            
            # Wait for the command to complete
            max_retries = 10
            retry_count = 0
            
            while retry_count < max_retries:
                time.sleep(2)
                result = ssm_client.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id
                )
                
                if result['Status'] in ['Success']:
                    logger.info(f"Successfully pushed public key to instance {instance_id}")
                    return True
                elif result['Status'] in ['Failed', 'Cancelled', 'TimedOut']:
                    logger.error(f"Failed to push public key: {result.get('StatusDetails')}")
                    return False
                
                retry_count += 1
            
            logger.error(f"Timed out waiting for SSM command to complete")
            return False
        except Exception as e:
            logger.error(f"Error pushing public key via SSM: {str(e)}")
            return False
    
    def _try_ssm_port_forwarding(self, instance_id: str, region: str) -> Dict[str, Any]:
        """
        Set up SSM port forwarding to the instance
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            Dictionary with SSH connection details if successful, empty dict otherwise
        """
        try:
            ssm_client = self._get_ssm_client(region)
            
            # Start the SSM session (port forwarding to 22)
            response = ssm_client.start_session(
                Target=instance_id,
                DocumentName='AWS-StartPortForwardingSession',
                Parameters={
                    'portNumber': ['22'],
                    'localPortNumber': ['0']  # Use any available local port
                }
            )
            
            # Extract the local port
            session_id = response['SessionId']
            local_port = int(response.get('StreamUrl', '').split(':')[-1])
            
            if not local_port:
                logger.error("Failed to determine local port for SSM tunnel")
                return {}
            
            # Generate a temporary key pair for the connection
            key_name, private_key = self._create_key_pair(instance_id, region)
            
            if not key_name or not private_key:
                logger.error("Failed to create key pair for SSM connection")
                return {}
            
            # Determine the default username
            instance_details = self._get_instance_details(instance_id, region)
            username = self._determine_username(
                instance_details.get('ami_id', ''),
                instance_details.get('platform', '')
            )
            
            return {
                "username": username,
                "private_key": private_key,
                "port": local_port,
                "host": "localhost",
                "ssm_session_id": session_id,
                "connection_type": "ssm_port_forwarding"
            }
        except Exception as e:
            logger.error(f"Error setting up SSM port forwarding: {str(e)}")
            return {}
    
    def _try_ssh_username_password(self, instance_id: str, region: str) -> Dict[str, Any]:
        """
        Try to connect using username/password from user data or from secrets
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            
        Returns:
            Dictionary with SSH connection details if successful, empty dict otherwise
        """
        # This is a placeholder - in a real implementation you would:
        # 1. Try to retrieve password from Secrets Manager
        # 2. Check if password was set in user data
        # 3. Try default passwords for AMIs that have them
        
        # For now we'll just return an empty dict
        return {}
    
    def setup_ssh_access(self, instance_id: str, region: str, strategy: str = "auto") -> Dict[str, Any]:
        """
        Set up SSH access to an EC2 instance using the specified strategy
        
        Args:
            instance_id: EC2 instance ID
            region: AWS region
            strategy: SSH setup strategy (auto, keypair, ssm, authorized_keys)
            
        Returns:
            Dictionary with SSH connection details if successful, empty dict otherwise
        """
        logger.info(f"Setting up SSH access for EC2 instance {instance_id} using strategy: {strategy}")
        
        # Get instance details
        instance_details = self._get_instance_details(instance_id, region)
        
        if not instance_details:
            logger.error(f"Unable to get details for instance {instance_id}")
            return {}
        
        # Determine username based on AMI
        username = self._determine_username(
            instance_details.get('ami_id', ''),
            instance_details.get('platform', '')
        )
        
        # Strategies to try (in order of preference)
        strategies_to_try = []
        
        if strategy == "auto":
            # Auto-determine the best strategy
            if instance_details.get('ssm_enabled', False):
                strategies_to_try = ["ssm", "keypair", "authorized_keys"]
            else:
                strategies_to_try = ["keypair", "authorized_keys"]
        else:
            # Use the specified strategy
            strategies_to_try = [strategy]
        
        # Try each strategy in order
        for strat in strategies_to_try:
            logger.info(f"Trying SSH strategy: {strat} for instance {instance_id}")
            
            if strat == "ssm":
                # Try SSM port forwarding
                if instance_details.get('ssm_enabled', False):
                    result = self._try_ssm_port_forwarding(instance_id, region)
                    if result:
                        logger.info(f"SSM port forwarding successful for instance {instance_id}")
                        return result
            
            elif strat == "keypair":
                # Try using the instance's key pair
                key_name = instance_details.get('key_name')
                
                if key_name:
                    try:
                        # Try to get the private key from the credential store or parameter store
                        private_key = self._get_private_key_for_key_name(key_name, region)
                        
                        if private_key:
                            logger.info(f"Found private key for key pair {key_name}")
                            return {
                                "username": username,
                                "private_key": private_key,
                                "port": 22,
                                "host": instance_details.get('public_ip'),
                                "connection_type": "ssh_keypair"
                            }
                    except Exception as e:
                        logger.error(f"Error retrieving key pair {key_name}: {str(e)}")
            
            elif strat == "authorized_keys":
                # Try pushing a new key via SSM and using it
                if instance_details.get('ssm_enabled', False):
                    key_name, private_key = self._create_key_pair(instance_id, region)
                    
                    if key_name and private_key:
                        if self._push_public_key_via_ssm(instance_id, region, key_name, private_key):
                            logger.info(f"Successfully pushed public key to instance {instance_id}")
                            return {
                                "username": username,
                                "private_key": private_key,
                                "port": 22,
                                "host": instance_details.get('public_ip'),
                                "connection_type": "ssh_authorized_keys"
                            }
        
        # If we get here, none of the strategies worked
        logger.error(f"All SSH strategies failed for instance {instance_id}")
        return {}
    
    def _get_private_key_for_key_name(self, key_name: str, region: str) -> Optional[str]:
        """
        Get the private key for a key pair name
        
        Args:
            key_name: Key pair name
            region: AWS region
            
        Returns:
            Private key if available, None otherwise
        """
        # Check if the key is in our credentials
        if 'key_pairs' in self.credentials:
            for key_pair in self.credentials['key_pairs']:
                if key_pair.get('name') == key_name:
                    return key_pair.get('private_key')
        
        # Check AWS Secrets Manager
        try:
            secrets_client = boto3.client(
                'secretsmanager',
                region_name=region,
                aws_access_key_id=self.credentials.get('aws_access_key_id'),
                aws_secret_access_key=self.credentials.get('aws_secret_access_key')
            )
            
            response = secrets_client.get_secret_value(
                SecretId=f"ec2-keypair-{key_name}"
            )
            
            if 'SecretString' in response:
                return response['SecretString']
        except Exception as e:
            logger.debug(f"Error retrieving key from Secrets Manager: {str(e)}")
        
        # Key not found
        logger.warning(f"Private key for key pair {key_name} not found")
        return None