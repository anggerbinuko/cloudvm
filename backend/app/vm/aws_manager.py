import boto3
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class AwsVmManager:
    def __init__(self, credentials: Dict[str, Any]):
        """
        Inisialisasi manager VM AWS
        
        Args:
            credentials: Dictionary berisi kredensial AWS
        """
        self.aws_access_key_id = credentials.get("aws_access_key_id")
        self.aws_secret_access_key = credentials.get("aws_secret_access_key")
        self.region = credentials.get("aws_region", "us-east-1")
        
        logger.info(f"Initializing AWS manager with region: {self.region}")
        
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            logger.error("Missing AWS credentials")
            raise ValueError("AWS credentials are missing")
            
        # Inisialisasi klien EC2
        self.ec2_client = boto3.client(
            'ec2',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region
        )
        
        self.ec2_resource = boto3.resource(
            'ec2',
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region
        )
    
    def list_instances(self) -> List[Dict[str, Any]]:
        """
        Mendapatkan daftar instance EC2
        
        Returns:
            List of EC2 instances
        """
        try:
            # Test connection first
            logger.info(f"Testing AWS connection in region {self.region}")
            self.ec2_client.describe_regions()
            logger.info("AWS connection test successful")
            
            instances = []
            paginator = self.ec2_client.get_paginator('describe_instances')
            
            # Include all instance states
            filters = [
                {
                    'Name': 'instance-state-name',
                    'Values': ['pending', 'running', 'shutting-down', 'terminated', 'stopping', 'stopped']
                }
            ]
            
            try:
                logger.info(f"Fetching AWS instances in region {self.region}")
                for page in paginator.paginate(Filters=filters):
                    logger.debug(f"Processing page: {page}")
                    for reservation in page.get("Reservations", []):
                        for instance in reservation.get("Instances", []):
                            logger.info(f"Found instance: {instance.get('InstanceId')} in state {instance.get('State', {}).get('Name')}")
                            
                            # Get instance name from tags
                            name = None
                            for tag in instance.get("Tags", []):
                                if tag.get("Key") == "Name":
                                    name = tag.get("Value")
                                    break
                            
                            if not name:
                                name = instance.get("InstanceId")
                                
                            instance_data = {
                                "instance_id": instance.get("InstanceId"),
                                "name": name,
                                "state": instance.get("State", {}).get("Name"),
                                "instance_type": instance.get("InstanceType"),
                                "public_ip": instance.get("PublicIpAddress"),
                                "private_ip": instance.get("PrivateIpAddress")
                            }
                            instances.append(instance_data)
                            logger.info(f"Added instance to list: {instance_data}")
                
                logger.info(f"Total instances found in {self.region}: {len(instances)}")
                return instances
                
            except Exception as e:
                logger.error(f"Error fetching instances: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error in list_instances: {str(e)}")
            raise

    def start_instance(self, instance_id: str) -> None:
        """
        Start an EC2 instance
        
        Args:
            instance_id: ID of the instance to start
        """
        try:
            logger.info(f"Starting AWS instance {instance_id}")
            self.ec2_client.start_instances(InstanceIds=[instance_id])
            
            # Wait for the instance to be running
            waiter = self.ec2_client.get_waiter('instance_running')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 40}  # Wait up to ~3 minutes
            )
            logger.info(f"AWS instance {instance_id} is now running")
            
        except Exception as e:
            logger.error(f"Error starting AWS instance {instance_id}: {str(e)}")
            raise ValueError(f"Failed to start AWS instance: {str(e)}")

    def stop_instance(self, instance_id: str) -> None:
        """
        Stop an EC2 instance
        
        Args:
            instance_id: ID of the instance to stop
        """
        try:
            logger.info(f"Stopping AWS instance {instance_id}")
            self.ec2_client.stop_instances(InstanceIds=[instance_id])
            
            # Wait for the instance to be stopped
            waiter = self.ec2_client.get_waiter('instance_stopped')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 40}  # Wait up to ~3 minutes
            )
            logger.info(f"AWS instance {instance_id} is now stopped")
            
        except Exception as e:
            logger.error(f"Error stopping AWS instance {instance_id}: {str(e)}")
            raise ValueError(f"Failed to stop AWS instance: {str(e)}")

    def terminate_instance(self, instance_id: str) -> None:
        """
        Terminate an EC2 instance
        
        Args:
            instance_id: ID of the instance to terminate
        """
        try:
            logger.info(f"Terminating AWS instance {instance_id}")
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            
            # Wait for the instance to be terminated
            waiter = self.ec2_client.get_waiter('instance_terminated')
            waiter.wait(
                InstanceIds=[instance_id],
                WaiterConfig={'Delay': 5, 'MaxAttempts': 40}  # Wait up to ~3 minutes
            )
            logger.info(f"AWS instance {instance_id} has been terminated")
            
        except Exception as e:
            logger.error(f"Error terminating AWS instance {instance_id}: {str(e)}")
            raise ValueError(f"Failed to terminate AWS instance: {str(e)}")
