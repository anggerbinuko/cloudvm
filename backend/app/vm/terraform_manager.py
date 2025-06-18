import os
import json
import tempfile
import subprocess
import logging
import shutil
from typing import Dict, Any, Optional

from app.history.terraform import TerraformExecutor
from app.history.models import EventType

logger = logging.getLogger(__name__)

class TerraformManager:
    def __init__(self, terraform_dir: str):
        """
        Inisialisasi Terraform Manager
        
        Args:
            terraform_dir: Direktori tempat file Terraform berada
        """
        self.terraform_dir = terraform_dir
        self._last_terraform_dir = None  # Untuk tracking direktori terraform terakhir
        self._last_command_output = None  # Untuk menyimpan output terakhir
    
    def _create_vars_file(self, vars_data: Dict[str, Any], provider: str) -> str:
        """
        Membuat file terraform.tfvars.json
        
        Args:
            vars_data: Data variabel Terraform
            provider: Provider cloud (aws/gcp)
            
        Returns:
            Path ke direktori kerja
        """
        # Buat direktori kerja
        work_dir = os.path.join(tempfile.gettempdir(), f"terraform_{provider}_{os.urandom(8).hex()}")
        os.makedirs(work_dir, exist_ok=True)
        
        # Salin file Terraform ke direktori kerja
        provider_dir = os.path.join(self.terraform_dir, provider)
        for filename in os.listdir(provider_dir):
            if filename.endswith('.tf'):
                src_path = os.path.join(provider_dir, filename)
                dst_path = os.path.join(work_dir, filename)
                with open(src_path, 'r') as src, open(dst_path, 'w') as dst:
                    dst.write(src.read())
        
        # Buat file tfvars
        tfvars_path = os.path.join(work_dir, "terraform.tfvars.json")
        with open(tfvars_path, 'w') as f:
            json.dump(vars_data, f)
        
        return work_dir
    
    def apply_aws(self, vm_data: Dict[str, Any], credentials: Dict[str, Any], vm_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Menerapkan konfigurasi Terraform untuk AWS
        
        Args:
            vm_data: Data VM yang akan dibuat
            credentials: Kredensial AWS yang telah didekripsi
            vm_id: ID VM (opsional)
            
        Returns:
            Detail instance yang dibuat
        """
        logger.info(f"Starting AWS VM deployment with Terraform for VM ID: {vm_id}")
        
        try:
            # Siapkan variabel Terraform
            logger.info("Preparing AWS variables...")
            # Pastikan credentials berisi access_key dan secret_key
            if not credentials.get("aws_access_key_id") or not credentials.get("aws_secret_access_key"):
                logger.error("Missing required AWS credentials (access_key or secret_key)")
                raise ValueError("Missing required AWS credentials")
            
            # Map region to AMI ID (Amazon Linux 2023)
            region_to_ami = {
                "ap-southeast-1": "ami-0df7a207adb9748c7",  # Singapore
                "ap-southeast-2": "ami-04f5097681773b989",  # Sydney
                "ap-northeast-1": "ami-0ed99df77a82560e6",  # Tokyo
                "us-east-1": "ami-0230bd60aa48260c6",      # N. Virginia
                "us-east-2": "ami-0cf0e376c672104d6",      # Ohio
                "us-west-1": "ami-0ce2cb35386fc22e9",      # N. California
                "us-west-2": "ami-008fe2fc65df48dac",      # Oregon
                "eu-west-1": "ami-0694d931cee176e7d",      # Ireland
                "eu-central-1": "ami-0292a6e27847c9582",   # Frankfurt
            }
            
            # Get region from credentials or vm_data
            region = credentials.get("aws_region") or vm_data.get("region", "us-east-1")
            ami_id = region_to_ami.get(region, "ami-0df7a207adb9748c7")  # Default to Singapore if region not found
            
            logger.info(f"Using AMI ID {ami_id} for region {region}")
                
            vars_data = {
                "access_key": credentials.get("aws_access_key_id"),
                "secret_key": credentials.get("aws_secret_access_key"),
                "region": region,
                "name": vm_data.get("name"),
                "instance_type": vm_data.get("instance_type", "t2.micro"),
                "ami_id": ami_id,
                "key_name": vm_data.get("key_name"),
                "security_group_ids": vm_data.get("security_group_ids", []),
                "storage_size": vm_data.get("storage_size", 8),
                "environment": vm_data.get("environment", "development")
            }
            
            logger.info(f"AWS variables prepared with region: {vars_data['region']}, instance type: {vars_data['instance_type']}")
            
            # Buat direktori kerja dan file tfvars
            work_dir = self._create_vars_file(vars_data, "aws")
            logger.info(f"Created Terraform working directory at: {work_dir}")
            
            # Jalankan Terraform init
            logger.info("Running Terraform init...")
            init_process = subprocess.run(
                ["terraform", "init"],
                cwd=work_dir,
                capture_output=True,
            text=True
            )
            
            if init_process.returncode != 0:
                logger.error(f"Terraform init failed with return code {init_process.returncode}")
                logger.error(f"Terraform init stderr: {init_process.stderr}")
                raise Exception(f"Terraform init failed: {init_process.stderr}")
                
            logger.info("Terraform init completed successfully")
                
                # Jalankan Terraform apply
            logger.info("Running Terraform apply...")
            apply_process = subprocess.run(
                    ["terraform", "apply", "-auto-approve"],
                    cwd=work_dir,
                    capture_output=True,
                text=True
            )
            
            if apply_process.returncode != 0:
                logger.error(f"Terraform apply failed with return code {apply_process.returncode}")
                logger.error(f"Terraform apply stderr: {apply_process.stderr}")
                raise Exception(f"Terraform apply failed: {apply_process.stderr}")
                
            logger.info("Terraform apply completed successfully")
            
            # Dapatkan output
            logger.info("Getting Terraform outputs...")
            output_process = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=work_dir,
                capture_output=True,
            text=True
            )
            
            if output_process.returncode != 0:
                logger.error(f"Terraform output failed: {output_process.stderr}")
                raise Exception(f"Could not get Terraform outputs: {output_process.stderr}")
            
            # Parse output
            try:
                logger.info("Parsing Terraform outputs...")
                output = json.loads(output_process.stdout)
                
                result = {
                    "instance_id": output.get("instance_id", {}).get("value"),
                    "public_ip": output.get("public_ip", {}).get("value"),
                    "private_ip": output.get("private_ip", {}).get("value"),
                    "status": "RUNNING"
                }
                logger.info(f"AWS VM deployment successful. Result: {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Terraform output: {str(e)}")
                logger.error(f"Raw output: {output_process.stdout}")
                raise Exception(f"Failed to parse Terraform output: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in AWS VM deployment: {str(e)}")
            # Simpan stdout dan stderr untuk debugging
            if 'apply_process' in locals():
                logger.error(f"Terraform apply stdout: {apply_process.stdout}")
                logger.error(f"Terraform apply stderr: {apply_process.stderr}")
            raise
    
    def destroy_aws(self, workspace_name: str, db=None, user_id: Optional[int] = None, vm_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Menghapus instance AWS menggunakan Terraform
        
        Args:
            workspace_name: Nama workspace Terraform
            db: Session database (opsional)
            user_id: ID pengguna (opsional)
            vm_id: ID VM (opsional)
            
        Returns:
            Status penghapusan
        """
        # Dapatkan direktori workspace
        workspace_dir = os.path.join(self.terraform_dir, "workspaces", workspace_name)
        
        if not os.path.exists(workspace_dir):
            raise Exception(f"Workspace {workspace_name} tidak ditemukan")
        
        try:
            if db and user_id:
                # Gunakan TerraformExecutor untuk mencatat history
                executor = TerraformExecutor(db, user_id, vm_id)
                success, result = executor.execute(
                    command="destroy",
                    working_dir=workspace_dir,
                    event_type=EventType.VM_DELETE
                )
                
                if not success:
                    raise Exception(f"Terraform destroy gagal: {result.get('stderr')}")
                
                return {"status": "destroyed"}
            else:
                # Jalankan Terraform tanpa mencatat history
                # Inisialisasi Terraform
                init_process = subprocess.run(
                    ["terraform", "init"],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Terraform init output: {init_process.stdout}")
                
                # Jalankan Terraform destroy
                process = subprocess.run(
                    ["terraform", "destroy", "-auto-approve"],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Terraform destroy output: {process.stdout}")
                
                return {"status": "destroyed"}
        finally:
            # Bersihkan direktori workspace jika diperlukan
            # shutil.rmtree(workspace_dir)
            pass
    
    def _get_gcp_machine_type(self, resources: Dict[str, Any]) -> str:
        """
        Mengkonversi spesifikasi resources menjadi tipe mesin GCP
        
        Args:
            resources: Dictionary berisi spesifikasi resources (cpu, memory, storage)
            
        Returns:
            String tipe mesin GCP yang sesuai
        """
        cpu = resources.get("cpu", 1)
        # Periksa baik 'memory' maupun 'ram' untuk backward compatibility
        memory = resources.get("memory", resources.get("ram", 1))
        
        # Tambahkan log untuk debugging
        logger.info(f"Converting resources to machine type: CPU={cpu}, Memory={memory}")
        
        # Mapping CPU dan memory ke tipe mesin GCP
        if cpu <= 1 and memory <= 1:
            return "e2-micro"
        elif cpu <= 2 and memory <= 4:
            return "e2-small"
        elif cpu <= 4 and memory <= 8:
            return "e2-medium"
        elif cpu <= 8 and memory <= 16:
            return "e2-standard-4"
        else:
            return "e2-standard-8"

    def apply_gcp(self, vm_data: Dict[str, Any], credentials: Dict[str, Any], vm_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Menerapkan konfigurasi Terraform untuk GCP
        
        Args:
            vm_data: Data VM yang akan dibuat
            credentials: Kredensial GCP yang telah didekripsi
            vm_id: ID VM (opsional)
            
        Returns:
            Detail instance yang dibuat
        """
        logger.info(f"Starting GCP VM deployment with Terraform for VM ID: {vm_id}")
        logger.info(f"VM data keys: {list(vm_data.keys())}")
        if 'resources' in vm_data:
            logger.info(f"Resources: {vm_data['resources']}")
        
        try:
            # Ekstrak service_account_json dari credentials yang didekripsi
            service_account_key = None
            project_id = None
            
            # Log struktur credentials untuk debugging
            logger.debug(f"Credential keys: {list(credentials.keys())}")
            
            # Format 1: Langsung
            if "gcp_service_account_json" in credentials:
                service_account_key = credentials["gcp_service_account_json"]
                project_id = credentials.get("gcp_project_id")
                logger.info("Using Format 1 (direct credentials)")
                
            # Format 2: Nested dalam gcp_credentials
            elif "gcp_credentials" in credentials:
                gcp_creds = credentials["gcp_credentials"]
                service_account_key = gcp_creds.get("gcp_service_account_json")
                project_id = gcp_creds.get("gcp_project_id")
                logger.info("Using Format 2 (nested credentials)")
            
            # Format 3: Jika sudah berupa objek service account
            elif "project_id" in credentials and "private_key" in credentials:
                service_account_key = credentials
                project_id = credentials.get("project_id")
                logger.info("Using Format 3 (direct service account)")
            
            # Format 4: Dari decrypted_data (format JSON string)
            elif "decrypted_data" in credentials:
                try:
                    decrypted_json = json.loads(credentials["decrypted_data"])
                    logger.info(f"Found decrypted_data, keys: {list(decrypted_json.keys())}")
                    
                    if "gcp_service_account_json" in decrypted_json:
                        service_account_key = decrypted_json["gcp_service_account_json"]
                        project_id = decrypted_json.get("gcp_project_id")
                        logger.info("Using Format 4 (from decrypted_data)")
                except Exception as e:
                    logger.error(f"Error parsing decrypted_data: {str(e)}")
            
            # Format 5: Dari service_account_key (langsung)
            elif "service_account_key" in credentials:
                service_account_key = credentials["service_account_key"]
                # Jika service_account_key sudah berupa dict, ekstrak project_id
                if isinstance(service_account_key, dict):
                    project_id = service_account_key.get("project_id")
                logger.info("Using Format 5 (from service_account_key)")
            
            # Format 6: Langsung dari key, value yang dikirim frontend
            elif "key" in credentials and credentials.get("type") == "GCP":
                try:
                    # Pastikan key adalah json string valid
                    if isinstance(credentials["key"], str):
                        service_account_key = json.loads(credentials["key"])
                        project_id = service_account_key.get("project_id")
                        logger.info("Using Format 6 (from key)")
                except Exception as e:
                    logger.error(f"Error parsing credentials key: {str(e)}")
                
            if not service_account_key:
                logger.error("Service account key not found in credentials")
                logger.error(f"Available credential keys: {list(credentials.keys())}")
                raise ValueError("Service account key not found in credentials")
            
            # Pastikan service_account_key adalah objek dict
            if isinstance(service_account_key, str):
                try:
                    logger.info("Converting service_account_key from string to JSON")
                    service_account_key = json.loads(service_account_key)
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing service_account_key: {str(e)}")
                    raise ValueError("Format JSON kredensial GCP tidak valid")
            
            if not isinstance(service_account_key, dict):
                logger.error(f"Service account key is not a dictionary: {type(service_account_key)}")
                raise ValueError("Format service_account_key harus berupa objek JSON")
            
            # Validasi field yang diperlukan
            required_fields = [
                "type", "project_id", "private_key_id", "private_key",
                "client_email", "client_id"
            ]
            
            missing_fields = [field for field in required_fields if field not in service_account_key]
            if missing_fields:
                logger.error(f"Missing required fields in service_account_key: {missing_fields}")
                raise ValueError(f"Service account key tidak lengkap. Field yang kurang: {', '.join(missing_fields)}")
            
            # Gunakan project_id dari service_account_key jika tidak ada
            if not project_id:
                project_id = service_account_key.get("project_id")
                logger.info(f"Using project_id from service_account_key: {project_id}")
            
            if not project_id:
                logger.error("Missing project_id in GCP credentials")
                raise ValueError("Missing project_id in GCP credentials")
            
            # Tentukan zone berdasarkan region
            region = vm_data.get("region", "us-central1")
            # Jika zone tidak disediakan, gunakan region + "-a"
            zone = vm_data.get("zone", f"{region}-a")
            logger.info(f"Using region: {region}, zone: {zone}")
            
            # Dapatkan resources
            resources = vm_data.get("resources", {})
            if not resources:
                logger.warning("No resources provided, using default values")
                resources = {"cpu": 1, "memory": 1, "storage": 10}
            
            # Normalisasi field memory/ram
            if "ram" in resources and "memory" not in resources:
                resources["memory"] = resources["ram"]
                logger.info(f"Normalized 'ram' to 'memory': {resources['memory']}")
            
            # Tentukan tipe mesin dari instance_type atau dari resources
            machine_type = vm_data.get("instance_type")
            if not machine_type and resources:
                machine_type = self._get_gcp_machine_type(resources)
                logger.info(f"Derived machine_type from resources: {machine_type}")
            elif not machine_type:
                machine_type = "e2-micro"  # Default machine type
                logger.info(f"Using default machine_type: {machine_type}")
            
            # Konversi service_account_key ke string JSON
            service_account_json_str = json.dumps(service_account_key)
            logger.info(f"Service account JSON string length: {len(service_account_json_str)}")
            
            # Tentukan image berdasarkan input atau gunakan default
            image = vm_data.get("image", "debian-cloud/debian-12-bookworm")
            
            # Pastikan disk_size adalah angka
            disk_size = 10  # Default
            if resources:
                # Ambil dari resources.storage jika tersedia
                if "storage" in resources:
                    try:
                        disk_size = int(resources["storage"])
                        logger.info(f"Using disk_size from resources.storage: {disk_size}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to convert resources.storage to int: {e}, using default")
                # Fallback ke disk_size jika ada
                elif "disk_size" in vm_data:
                    try:
                        disk_size = int(vm_data["disk_size"])
                        logger.info(f"Using disk_size directly from vm_data: {disk_size}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to convert disk_size to int: {e}, using default")
            
            # Tentukan preset berdasarkan input atau gunakan default
            preset = vm_data.get("preset", "custom")
            logger.info(f"Using preset: {preset}")
            
            # Siapkan data Terraform variables
            vars_data = {
                "credentials_json": service_account_json_str,
                "project_id": project_id,
                "region": region,
                "zone": zone,
                "name": vm_data.get("name"),
                "machine_type": machine_type,
                "image": image,
                "disk_size": disk_size,
                "preset": preset
            }
            
            # Tambahkan nilai tambahan jika tersedia
            if "network" in vm_data:
                network_config = vm_data["network"]
                logger.info(f"Network configuration: {network_config}")
                # Tambah public_ip ke vars_data jika disediakan
                if isinstance(network_config, dict) and "public_ip" in network_config:
                    vars_data["public_ip"] = network_config["public_ip"]
                    logger.info(f"Added public_ip setting: {vars_data['public_ip']}")
            
            logger.info(f"GCP variables prepared with region: {vars_data['region']}, zone: {vars_data['zone']}, machine type: {vars_data['machine_type']}, disk size: {vars_data['disk_size']}, preset: {vars_data['preset']}")
            
            # Buat direktori kerja dan file tfvars
            work_dir = self._create_vars_file(vars_data, "gcp")
            logger.info(f"Created Terraform working directory at: {work_dir}")
            
            # Simpan direktori terakhir untuk debugging
            self._last_terraform_dir = work_dir
            
            # Cek keberadaan file terraform
            tf_files = [f for f in os.listdir(work_dir) if f.endswith('.tf')]
            logger.info(f"Terraform files in working directory: {tf_files}")
            
            # Verifikasi file tfvars.json
            tfvars_path = os.path.join(work_dir, "terraform.tfvars.json")
            if os.path.exists(tfvars_path):
                with open(tfvars_path, 'r') as f:
                    tfvars_content = f.read()
                    logger.info(f"Terraform vars file created with length: {len(tfvars_content)} bytes")
                    # Verifikasi bahwa credentials_json valid
                    try:
                        tfvars = json.loads(tfvars_content)
                        if "credentials_json" in tfvars:
                            # Log panjang dan validitas credentials_json
                            cred_len = len(tfvars["credentials_json"])
                            logger.info(f"credentials_json length: {cred_len} chars")
                            
                            # Validasi credentials_json adalah JSON valid
                            try:
                                json.loads(tfvars["credentials_json"])
                                logger.info("credentials_json is valid JSON")
                            except json.JSONDecodeError as e:
                                logger.error(f"credentials_json is NOT valid JSON: {str(e)}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing tfvars.json: {str(e)}")
            else:
                logger.error(f"tfvars.json file not found at {tfvars_path}")
            
            # Jalankan Terraform init
            logger.info("Running Terraform init...")
            init_process = subprocess.run(
                ["terraform", "init"],
                cwd=work_dir,
                capture_output=True,
            text=True
            )
            
            if init_process.returncode != 0:
                logger.error(f"Terraform init failed with return code {init_process.returncode}")
                logger.error(f"Terraform init stderr: {init_process.stderr}")
                raise Exception(f"Terraform init failed: {init_process.stderr}")
                
            logger.info("Terraform init completed successfully")
                
                # Jalankan Terraform apply
            logger.info("Running Terraform apply...")
            apply_process = subprocess.run(
                    ["terraform", "apply", "-auto-approve"],
                    cwd=work_dir,
                    capture_output=True,
                text=True
            )
            
            if apply_process.returncode != 0:
                logger.error(f"Terraform apply failed with return code {apply_process.returncode}")
                logger.error(f"Terraform apply stderr: {apply_process.stderr}")
                raise Exception(f"Terraform apply failed: {apply_process.stderr}")
                
            logger.info("Terraform apply completed successfully")
            
            # Dapatkan output
            logger.info("Getting Terraform outputs...")
            output_process = subprocess.run(
                ["terraform", "output", "-json"],
                cwd=work_dir,
                capture_output=True,
            text=True
            )
            
            if output_process.returncode != 0:
                logger.error(f"Terraform output failed: {output_process.stderr}")
                raise Exception(f"Could not get Terraform outputs: {output_process.stderr}")
            
            # Parse output
            try:
                logger.info("Parsing Terraform outputs...")
                output = json.loads(output_process.stdout)
                
                # Handle different output keys from different templates
                instance_id = None
                public_ip = None
                private_ip = None
                
                # Check for output keys from low_cost template
                if "vm_name" in output:
                    instance_id = output.get("vm_name", {}).get("value")
                    
                if "external_ip" in output:
                    public_ip = output.get("external_ip", {}).get("value")
                elif "app_external_ip" in output:
                    public_ip = output.get("app_external_ip", {}).get("value")
                
                if "internal_ip" in output:
                    private_ip = output.get("internal_ip", {}).get("value")
                elif "app_internal_ip" in output:
                    private_ip = output.get("app_internal_ip", {}).get("value")
                
                # Jika tidak ditemukan, cek output keys dari main.tf
                if not instance_id and "instance_id" in output:
                    instance_id = output.get("instance_id", {}).get("value")
                
                # Jika masih tidak ditemukan, gunakan ID dari request
                if not instance_id:
                    logger.warning("Instance ID not found in Terraform output, using VM name instead")
                    instance_id = vm_data.get("name")
                
                # Build result
                result = {
                    "instance_id": instance_id,
                    "public_ip": public_ip,
                    "private_ip": private_ip,
                    "status": "RUNNING"
                }
                
                logger.info(f"GCP VM deployment successful. Result: {result}")
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Terraform output: {str(e)}")
                logger.error(f"Raw output: {output_process.stdout}")
                raise Exception(f"Failed to parse Terraform output: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error in GCP VM deployment: {str(e)}")
            # Simpan stdout dan stderr untuk debugging
            if 'apply_process' in locals():
                logger.error(f"Terraform apply stdout: {apply_process.stdout}")
                logger.error(f"Terraform apply stderr: {apply_process.stderr}")
            raise
            
        finally:
            # Bersihkan direktori kerja jika ada
            if 'work_dir' in locals():
                try:
                    shutil.rmtree(work_dir)
                    logger.info(f"Cleaned up working directory: {work_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up working directory: {str(e)}")
    
    def destroy_gcp(self, workspace_name: str, db=None, user_id: Optional[int] = None, vm_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Menghapus instance GCP menggunakan Terraform
        
        Args:
            workspace_name: Nama workspace Terraform
            db: Session database (opsional)
            user_id: ID pengguna (opsional)
            vm_id: ID VM (opsional)
            
        Returns:
            Status penghapusan
        """
        # Dapatkan direktori workspace
        workspace_dir = os.path.join(self.terraform_dir, "workspaces", workspace_name)
        
        if not os.path.exists(workspace_dir):
            raise Exception(f"Workspace {workspace_name} tidak ditemukan")
        
        try:
            if db and user_id:
                # Gunakan TerraformExecutor untuk mencatat history
                executor = TerraformExecutor(db, user_id, vm_id)
                success, result = executor.execute(
                    command="destroy",
                    working_dir=workspace_dir,
                    event_type=EventType.VM_DELETE
                )
                
                if not success:
                    raise Exception(f"Terraform destroy gagal: {result.get('stderr')}")
                
                return {"status": "destroyed"}
            else:
                # Jalankan Terraform tanpa mencatat history
                # Inisialisasi Terraform
                init_process = subprocess.run(
                    ["terraform", "init"],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Terraform init output: {init_process.stdout}")
                
                # Jalankan Terraform destroy
                process = subprocess.run(
                    ["terraform", "destroy", "-auto-approve"],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                logger.info(f"Terraform destroy output: {process.stdout}")
                
                return {"status": "destroyed"}
        finally:
            # Bersihkan direktori workspace jika diperlukan
            # shutil.rmtree(workspace_dir)
            pass 