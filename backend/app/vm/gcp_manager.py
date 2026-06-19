from google.oauth2 import service_account
from google.cloud import compute_v1
from typing import Dict, Any, List, Optional
import logging
import time

logger = logging.getLogger(__name__)

class GcpVmManager:
    def __init__(self, credentials: Dict[str, Any]):
        """
        Inisialisasi manager VM GCP
        
        Args:
            credentials: Dictionary berisi kredensial GCP
        """
        # Log kredensial keys untuk debugging (tanpa nilai)
        logger.info(f"GCP credentials keys: {list(credentials.keys())}")
        
        # Get decrypted data if available
        if 'decrypted_data' in credentials:
            credentials = credentials['decrypted_data']
            logger.info("Using decrypted_data from credentials")
            
        # Get project ID
        self.project_id = credentials.get('gcp_project_id')
        logger.info(f"Found project_id: {self.project_id}")
        
        # Get service account info
        if 'gcp_service_account_json' in credentials:
            self.service_account_info = credentials['gcp_service_account_json']
            logger.info("Found service account JSON in gcp_service_account_json")
        else:
            raise ValueError("GCP service account JSON tidak ditemukan dalam kredensial")
            
        # Validasi project ID
        if not self.project_id:
            raise ValueError("GCP project_id tidak ditemukan dalam kredensial")
            
        # Validasi service account info
        if not isinstance(self.service_account_info, dict):
            try:
                if isinstance(self.service_account_info, str):
                    import json
                    self.service_account_info = json.loads(self.service_account_info)
                    logger.info("Parsed service account JSON from string")
            except Exception as e:
                raise ValueError(f"Invalid service account JSON format: {str(e)}")
                
        # Log info credential yang akan digunakan
        logger.info(f"Using GCP project_id: {self.project_id}")
        
        # Buat kredensial dari service account info
        try:
            self.credentials = service_account.Credentials.from_service_account_info(
                self.service_account_info
            )
            logger.info("Successfully created GCP credentials from service account info")
            
            # Inisialisasi klien Compute Engine
            self.instance_client = compute_v1.InstancesClient(credentials=self.credentials)
            self.zone_client = compute_v1.ZonesClient(credentials=self.credentials)
            self.region_client = compute_v1.RegionsClient(credentials=self.credentials)
            self.machine_type_client = compute_v1.MachineTypesClient(credentials=self.credentials)
            self.image_client = compute_v1.ImagesClient(credentials=self.credentials)
            self.operation_client = compute_v1.ZoneOperationsClient(credentials=self.credentials)
            logger.info("Successfully initialized GCP clients")
            
            # Define default zones instead of scanning all zones
            self.default_zones = [
                # Asia zones
                "asia-southeast1-b",  # Singapore
                "asia-east1-b",       # Taiwan
                
                # US zones
                "us-central1-a",      # Iowa 
                "us-east1-b",         # South Carolina
                
                # Europe zones
                "europe-west2-a"      # London
            ]
            
        except Exception as e:
            logger.error(f"Error initializing GCP credentials: {str(e)}")
            raise ValueError(f"Gagal menginisialisasi kredensial GCP: {str(e)}")
    
    def list_instances(self, zone: str = "us-central1-a") -> List[Dict[str, Any]]:
        """
        Mendapatkan daftar instance VM
        
        Args:
            zone: Zona GCP
            
        Returns:
            List of VM instances
        """
        try:
            request = compute_v1.ListInstancesRequest(
                project=self.project_id,
                zone=zone
            )
            
            instances = []
            for instance in self.instance_client.list(request=request):
                instances.append({
                    "id": instance.id,
                    "name": instance.name,
                    "machine_type": instance.machine_type.split("/")[-1],
                    "zone": instance.zone.split("/")[-1],
                    "status": instance.status,
                    "network_interfaces": [
                        {
                            "network": ni.network.split("/")[-1],
                            "external_ip": ni.access_configs[0].nat_i_p if ni.access_configs else None,
                            "internal_ip": ni.network_i_p
                        } for ni in instance.network_interfaces
                    ],
                    "creation_timestamp": instance.creation_timestamp
                })
            
            return instances
        except Exception as e:
            logger.error(f"Error listing GCP instances: {str(e)}")
            raise
    
    def get_instance(self, name: str, zone: str = "us-central1-a") -> Optional[Dict[str, Any]]:
        """
        Mendapatkan detail instance VM
        
        Args:
            name: Nama instance
            zone: Zona GCP
            
        Returns:
            Instance details or None if not found
        """
        try:
            request = compute_v1.GetInstanceRequest(
                project=self.project_id,
                zone=zone,
                instance=name
            )
            
            instance = self.instance_client.get(request=request)
            
            return {
                "id": instance.id,
                "name": instance.name,
                "machine_type": instance.machine_type.split("/")[-1],
                "zone": instance.zone.split("/")[-1],
                "status": instance.status,
                "network_interfaces": [
                    {
                        "network": ni.network.split("/")[-1],
                        "external_ip": ni.access_configs[0].nat_i_p if ni.access_configs else None,
                        "internal_ip": ni.network_i_p
                    } for ni in instance.network_interfaces
                ],
                "creation_timestamp": instance.creation_timestamp
            }
        except Exception as e:
            logger.error(f"Error getting GCP instance {name}: {str(e)}")
            return None
    
    def create_instance(
        self,
        name: str,
        machine_type: str = "e2-micro",
        zone: str = "us-central1-a",
        image_project: str = "debian-cloud",
        image_family: str = "debian-11"
    ) -> Dict[str, Any]:
        """
        Membuat instance VM baru
        
        Args:
            name: Nama instance
            machine_type: Tipe mesin
            zone: Zona GCP
            image_project: Proyek image
            image_family: Keluarga image
            
        Returns:
            Created instance details
        """
        try:
            # Dapatkan image terbaru
            image_request = compute_v1.GetFromFamilyImageRequest(
                project=image_project,
                family=image_family
            )
            image = self.image_client.get_from_family(request=image_request)
            
            # Buat instance
            instance = compute_v1.Instance()
            instance.name = name
            instance.machine_type = f"zones/{zone}/machineTypes/{machine_type}"
            
            # Disk boot
            disk = compute_v1.AttachedDisk()
            disk.boot = True
            disk.auto_delete = True
            disk.initialize_params = compute_v1.AttachedDiskInitializeParams()
            disk.initialize_params.source_image = image.self_link
            instance.disks = [disk]
            
            # Network interface
            network_interface = compute_v1.NetworkInterface()
            network_interface.name = "global/networks/default"
            
            access_config = compute_v1.AccessConfig()
            access_config.name = "External NAT"
            access_config.type_ = "ONE_TO_ONE_NAT"
            access_config.network_tier = "PREMIUM"
            network_interface.access_configs = [access_config]
            
            instance.network_interfaces = [network_interface]
            
            # Buat request
            request = compute_v1.InsertInstanceRequest(
                project=self.project_id,
                zone=zone,
                instance_resource=instance
            )
            
            # Kirim request
            operation = self.instance_client.insert(request=request)
            
            # Tunggu operasi selesai
            while operation.status != compute_v1.Operation.Status.DONE:
                operation_request = compute_v1.GetZoneOperationRequest(
                    project=self.project_id,
                    zone=zone,
                    operation=operation.name
                )
                operation = self.operation_client.get(request=operation_request)
                time.sleep(1)
            
            # Dapatkan detail instance
            return self.get_instance(name, zone)
        except Exception as e:
            logger.error(f"Error creating GCP instance: {str(e)}")
            raise
    
    def wait_for_operation(self, operation, zone: str):
        """
        Wait for a GCP operation to complete
        """
        while True:
            result = self.operation_client.get(
                project=self.project_id,
                zone=zone,
                operation=operation.name
            )
            if result.status == compute_v1.Operation.Status.DONE:
                if result.error:
                    raise Exception(result.error.errors[0].message)
                return result
            time.sleep(5)  # Wait 5 seconds between checks

    def start_instance(self, instance_id: str, zone: str = "us-central1-a") -> None:
        """
        Start a GCP instance
        
        Args:
            instance_id: Name of the instance to start
            zone: GCP zone where the instance is located
        """
        try:
            logger.info(f"Starting GCP instance {instance_id} in zone {zone}")
            operation = self.instance_client.start(
                project=self.project_id,
                zone=zone,
                instance=instance_id
            )
            self.wait_for_operation(operation, zone)
            logger.info(f"GCP instance {instance_id} is now running")
            
        except Exception as e:
            logger.error(f"Error starting GCP instance {instance_id}: {str(e)}")
            raise ValueError(f"Failed to start GCP instance: {str(e)}")

    def stop_instance(self, instance_id: str, zone: str = "us-central1-a") -> None:
        """
        Stop a GCP instance
        
        Args:
            instance_id: Name of the instance to stop
            zone: GCP zone where the instance is located
        """
        try:
            logger.info(f"Stopping GCP instance {instance_id} in zone {zone}")
            operation = self.instance_client.stop(
                project=self.project_id,
                zone=zone,
                instance=instance_id
            )
            self.wait_for_operation(operation, zone)
            logger.info(f"GCP instance {instance_id} is now stopped")
            
        except Exception as e:
            logger.error(f"Error stopping GCP instance {instance_id}: {str(e)}")
            raise ValueError(f"Failed to stop GCP instance: {str(e)}")

    def delete_instance(self, instance_id: str, zone: str = "us-central1-a") -> None:
        """
        Delete a GCP instance
        
        Args:
            instance_id: Name of the instance to delete
            zone: GCP zone where the instance is located
        """
        try:
            logger.info(f"Deleting GCP instance {instance_id} in zone {zone}")
            operation = self.instance_client.delete(
                project=self.project_id,
                zone=zone,
                instance=instance_id
            )
            self.wait_for_operation(operation, zone)
            logger.info(f"GCP instance {instance_id} has been deleted")
            
        except Exception as e:
            logger.error(f"Error deleting GCP instance {instance_id}: {str(e)}")
            raise ValueError(f"Failed to delete GCP instance: {str(e)}")
    
    def list_all_instances(self) -> List[Dict[str, Any]]:
        """
        Mendapatkan semua instance VM di seluruh zona sekaligus menggunakan
        aggregatedList — hanya 1 API call, jauh lebih efisien dari loop per zona.

        Returns:
            List of VM instances dari semua zona
        """
        try:
            request = compute_v1.AggregatedListInstancesRequest(
                project=self.project_id
            )

            all_instances = []
            for zone_name, scoped_list in self.instance_client.aggregated_list(request=request):
                # scoped_list.instances hanya ada jika zona tersebut punya VM
                if scoped_list.instances:
                    for instance in scoped_list.instances:
                        all_instances.append({
                            "id": str(instance.id),
                            "name": instance.name,
                            "machine_type": instance.machine_type.split("/")[-1],
                            "zone": zone_name.replace("zones/", ""),
                            "status": instance.status,
                            "network_interfaces": [
                                {
                                    "network": ni.network.split("/")[-1],
                                    "external_ip": ni.access_configs[0].nat_i_p if ni.access_configs else None,
                                    "internal_ip": ni.network_i_p
                                } for ni in instance.network_interfaces
                            ],
                            "creation_timestamp": instance.creation_timestamp
                        })

            logger.info(f"aggregatedList found {len(all_instances)} instances across all zones")
            return all_instances

        except Exception as e:
            logger.error(f"Error listing all GCP instances via aggregatedList: {str(e)}")
            raise

    def list_zones(self, specified_zones=None) -> List[str]:
        """
        Mendapatkan daftar zona yang tersedia
        
        Args:
            specified_zones: Optional list of zones to return instead of scanning all zones
            
        Returns:
            List of zone names
        """
        # If specified zones are provided, return them directly without scanning
        if specified_zones:
            logger.info(f"Using specified zones: {specified_zones}")
            return specified_zones
            
        # Use the default zones defined in __init__
        logger.info(f"Using default zones instead of scanning all zones: {self.default_zones}")
        return self.default_zones