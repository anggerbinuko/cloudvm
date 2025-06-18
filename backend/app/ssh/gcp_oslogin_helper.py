"""
Helper untuk mengelola SSH keys pada GCP menggunakan OS Login API
dengan kemampuan cleanup untuk menghapus kunci lama.
"""
import logging
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
from google.cloud import oslogin_v1
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class GcpOsLoginHelper:
    """Helper class untuk mengelola SSH keys menggunakan OS Login API"""
    
    def __init__(self, credentials):
        """
        Initialize GCP OS Login Helper
        
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
        
        # Initialize OS Login client
        self.oslogin_client = oslogin_v1.OsLoginServiceClient(credentials=self.credentials)
    
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
    
    def clean_old_ssh_keys(self, max_keys_to_keep=3):
        """
        Hapus kunci SSH lama dari profil OS Login untuk mencegah error "Login profile size exceeds 32 KiB"
        
        Args:
            max_keys_to_keep: Jumlah maksimum kunci SSH yang dipertahankan (yang terbaru)
            
        Returns:
            Jumlah kunci yang dihapus
        """
        try:
            # Dapatkan service account email
            service_account_email = self.credentials.service_account_email
            logger.info(f"Cleaning old SSH keys for {service_account_email}")
            
            # Format parent resource name
            parent = f"users/{service_account_email}"
            
            # Dapatkan login profile
            login_profile = self.oslogin_client.get_login_profile(name=parent)
            
            # Kumpulkan semua kunci SSH
            ssh_keys = []
            if login_profile and login_profile.ssh_public_keys:
                for fingerprint, key_data in login_profile.ssh_public_keys.items():
                    ssh_keys.append({
                        'fingerprint': fingerprint,
                        'key': key_data.key,
                        'expiration_time_usec': key_data.expiration_time_usec
                    })
            
            # Jika jumlah kunci kurang dari atau sama dengan batas, tidak perlu menghapus
            if len(ssh_keys) <= max_keys_to_keep:
                logger.info(f"Only {len(ssh_keys)} SSH keys found, no cleanup needed")
                return 0
                
            # Urutkan kunci berdasarkan waktu kedaluwarsa (None di akhir)
            ssh_keys.sort(key=lambda k: (k['expiration_time_usec'] or float('inf')))
            
            # Hitung jumlah kunci yang akan dihapus
            num_keys_to_delete = len(ssh_keys) - max_keys_to_keep
            keys_to_delete = ssh_keys[:num_keys_to_delete]
            
            # Hapus kunci lama
            deleted_count = 0
            for key in keys_to_delete:
                logger.info(f"Deleting SSH key with fingerprint: {key['fingerprint']}")
                self.oslogin_client.delete_ssh_public_key(name=f"{parent}/sshPublicKeys/{key['fingerprint']}")
                deleted_count += 1
                
            logger.info(f"Deleted {deleted_count} old SSH keys")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning old SSH keys: {str(e)}")
            return 0
    
    def add_ssh_key(self):
        """
        Add SSH key menggunakan OS Login API
            
        Returns:
            Dictionary dengan informasi SSH jika berhasil, None jika gagal
        """
        try:
            # Coba bersihkan kunci SSH lama terlebih dahulu
            self.clean_old_ssh_keys()
            
            # Generate a new SSH key pair
            private_key, public_key = self.generate_ssh_key_pair()
            
            # Dapatkan service account email dari credentials
            service_account_email = self.credentials.service_account_email
            logger.info(f"Using service account email: {service_account_email}")
            
            # Format parent resource name untuk OS Login API
            parent = f"users/{service_account_email}"
            
            # Buat SSH public key request
            ssh_public_key = {
                "key": public_key,
                "expiration_time_usec": None  # Tidak ada expiration time
            }
            
            # Import SSH public key ke OS Login
            logger.info(f"Importing SSH key for {parent}")
            response = self.oslogin_client.import_ssh_public_key(
                request={
                    "parent": parent,
                    "ssh_public_key": ssh_public_key
                }
            )
            
            logger.info(f"SSH key imported successfully: {response.login_profile.name}")
            
            # Ekstrak username OS Login dari login profile
            username = None
            if response.login_profile and response.login_profile.posix_accounts:
                for account in response.login_profile.posix_accounts:
                    if account.username:
                        username = account.username
                        logger.info(f"Found OS Login username: {username}")
                        break
            
            # Jika tidak ada username di login profile, gunakan format default untuk service account
            if not username:
                # Format username OS Login untuk service account
                # Format: sa_<numeric_id>@project-id.iam.gserviceaccount.com
                # Contoh: sa_123456789@my-project.iam.gserviceaccount.com
                username = service_account_email
                logger.info(f"Using service account email as username: {username}")
            
            # Return SSH connection details
            return {
                "username": username,
                "private_key": private_key,
                "public_key": public_key
            }
            
        except Exception as e:
            logger.error(f"Error setting up SSH access with OS Login: {str(e)}")
            return None
    
    def setup_ssh_access(self, instance_name, zone):
        """
        Set up SSH access to a GCP instance menggunakan OS Login
        
        Args:
            instance_name: Name of the instance (tidak digunakan untuk OS Login)
            zone: Zone where the instance is located (tidak digunakan untuk OS Login)
            
        Returns:
            Dictionary dengan informasi SSH
        """
        try:
            # Untuk OS Login, kita tidak perlu instance_name atau zone
            # Kita hanya perlu menambahkan SSH key ke akun pengguna
            logger.info(f"Setting up SSH access with OS Login for project {self.project_id}")
            
            # Tambahkan SSH key
            ssh_info = self.add_ssh_key()
            
            if not ssh_info:
                logger.error("Failed to add SSH key with OS Login")
                return None
            
            logger.info("SSH access set up successfully with OS Login")
            return ssh_info
            
        except Exception as e:
            logger.error(f"Error setting up SSH access: {str(e)}")
            return None