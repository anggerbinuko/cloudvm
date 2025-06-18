import os
import json
import base64
import logging
import hashlib
from typing import Any
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from app.config import settings

logger = logging.getLogger(__name__)

def get_encryption_key():
    """
    Derive an encryption key from the settings
    """
    if not settings.CREDENTIALS_ENCRYPTION_KEY:
        raise ValueError("CREDENTIALS_ENCRYPTION_KEY not set in environment variables")
    
    # Use a hash of the settings key to ensure proper length
    return hashlib.sha256(settings.CREDENTIALS_ENCRYPTION_KEY.encode()).digest()

def encrypt_credentials(data: Any) -> str:
    """
    Enkripsi data kredensial
    
    Args:
        data: Data yang akan dienkripsi (dict atau string)
        
    Returns:
        String terenkripsi dalam format base64
    """
    try:
        # Pastikan data dalam format JSON string
        if isinstance(data, dict):
            data_str = json.dumps(data)
        elif isinstance(data, str):
            # Pastikan string adalah JSON valid
            try:
                json.loads(data)  # Hanya untuk validasi
                data_str = data
            except json.JSONDecodeError:
                logger.error("Input string is not valid JSON")
                data_str = json.dumps({"raw": data})  # Wrap non-JSON string
        else:
            logger.error(f"Unsupported data type for encryption: {type(data)}")
            data_str = json.dumps(str(data))
            
        logger.debug(f"Data to encrypt length: {len(data_str)}")
        
        # Get encryption key
        key = get_encryption_key()
        
        # Generate random IV
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        # Pad the data
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data_str.encode()) + padder.finalize()
        
        # Encrypt
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV and encrypted data and encode with base64
        combined = iv + encrypted_data
        encoded = base64.b64encode(combined).decode()
        
        return encoded
    except Exception as e:
        logger.error(f"Error encrypting credentials: {str(e)}")
        raise ValueError(f"Failed to encrypt credentials: {str(e)}")

def decrypt_credentials(encrypted_data: str) -> Any:
    """
    Dekripsi data kredensial
    
    Args:
        encrypted_data: Data terenkripsi dalam format base64
        
    Returns:
        Data yang telah didekripsi
    """
    try:
        # Log input untuk debug
        logger.debug(f"Attempting to decrypt data of length: {len(encrypted_data)}")
        
        # Decode base64
        try:
            decoded = base64.b64decode(encrypted_data)
            logger.debug(f"Successfully decoded base64 data, length: {len(decoded)}")
        except Exception as e:
            logger.error(f"Base64 decode error: {str(e)}")
            raise
        
        # Extract IV and data
        iv = decoded[:16]
        cipher_text = decoded[16:]
        
        # Get encryption key
        key = get_encryption_key()
        logger.debug(f"Using encryption key (hash): {hashlib.md5(key).hexdigest()}")
        
        # Decrypt
        try:
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(cipher_text) + decryptor.finalize()
            logger.debug("AES decryption completed successfully")
        except Exception as e:
            logger.error(f"AES decryption error: {str(e)}")
            raise
        
        # Unpad
        try:
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded_data) + unpadder.finalize()
            logger.debug("Unpadding completed successfully")
        except Exception as e:
            logger.error(f"Unpadding error: {str(e)}")
            raise
            
        # Decode JSON
        data_str = data.decode()
        logger.debug(f"Decrypted data length: {len(data_str)}")
        logger.debug(f"Decrypted data first 50 chars: {data_str[:50]}...")
        
        try:
            # Coba parse sebagai JSON
            result = json.loads(data_str)
            logger.debug("Successfully parsed decrypted data as JSON")
            
            # Handle GCP credentials special case
            if isinstance(result, dict) and 'gcp_service_account_json' in result:
                if isinstance(result['gcp_service_account_json'], str):
                    try:
                        # Coba parse gcp_service_account_json jika dalam bentuk string
                        result['gcp_service_account_json'] = json.loads(result['gcp_service_account_json'])
                        logger.debug("Successfully parsed gcp_service_account_json back to dict")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing gcp_service_account_json: {str(e)}")
                        # Tetap gunakan string jika parsing gagal
            
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"Decrypted data is not valid JSON: {str(e)}")
            return data_str  # Return string langsung jika bukan JSON
            
    except ValueError as e:
        logger.error(f"Error decrypting credentials (value error): {str(e)}")
        raise ValueError(f"Failed to decrypt credentials: {str(e)}")
    except Exception as e:
        logger.error(f"Error decrypting credentials: {str(e)}")
        raise ValueError(f"Error decrypting credential: {str(e)}")

def mask_sensitive_data(data, mask_char="*", show_chars=4):
    """
    Mask sensitive data for logging or display
    
    Args:
        data (dict): Dictionary containing sensitive data
        mask_char (str): Character to use for masking
        show_chars (int): Number of characters to show at the end
        
    Returns:
        dict: Dictionary with sensitive data masked
    """
    if not isinstance(data, dict):
        return data
    
    masked_data = data.copy()
    
    sensitive_keys = [
        "aws_secret_access_key", 
        "private_key", 
        "password", 
        "secret", 
        "token"
    ]
    
    for key, value in masked_data.items():
        if isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, mask_char, show_chars)
        elif isinstance(value, str) and any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            if len(value) <= show_chars:
                masked_data[key] = mask_char * len(value)
            else:
                masked_data[key] = mask_char * (len(value) - show_chars) + value[-show_chars:]
    
    return masked_data