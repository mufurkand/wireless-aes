import base64
import os
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class AESCipher:
    def __init__(self, password):
        """Initialize AES cipher with password."""
        self.password = password.encode('utf-8')
        self.salt = os.urandom(16)  # Generate random salt
        self.key = self._derive_key(self.password, self.salt)
    
    def _derive_key(self, password, salt):
        """Derive key from password and salt using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 32 bytes for AES-256
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(password)
    
    def encrypt(self, data):
        """Encrypt data using AES-CBC mode."""
        iv = os.urandom(16)  # Generate random IV
        encryptor = Cipher(
            algorithms.AES(self.key),
            modes.CBC(iv),
            backend=default_backend()
        ).encryptor()
        
        # Ensure data is padded to be a multiple of 16 bytes
        padded_data = self._pad(data)
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Return salt + iv + encrypted data
        return base64.b64encode(self.salt + iv + encrypted_data)
    
    def decrypt(self, encrypted_data):
        """Decrypt data using AES-CBC mode."""
        encrypted_data = base64.b64decode(encrypted_data)
        
        # Extract salt, iv, and encrypted data
        salt = encrypted_data[:16]
        iv = encrypted_data[16:32]
        encrypted_data = encrypted_data[32:]
        
        # Derive key using the extracted salt
        key = self._derive_key(self.password, salt)
        
        decryptor = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        ).decryptor()
        
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Remove padding
        return self._unpad(decrypted_data)
    
    def _pad(self, data):
        """PKCS#7 padding."""
        if not isinstance(data, bytes):
            data = data.encode('utf-8')
            
        padding_length = 16 - (len(data) % 16)
        padding = bytes([padding_length]) * padding_length
        return data + padding
    
    def _unpad(self, data):
        """Remove PKCS#7 padding."""
        padding_length = data[-1]
        return data[:-padding_length]


def encrypt_file(input_file, output_file, password):
    """Encrypt a file using AES."""
    cipher = AESCipher(password)
    
    with open(input_file, 'rb') as f:
        file_data = f.read()
    
    encrypted_data = cipher.encrypt(file_data)
    
    with open(output_file, 'wb') as f:
        f.write(encrypted_data)


def decrypt_file(input_file, output_file, password):
    """Decrypt a file using AES."""
    cipher = AESCipher(password)
    
    with open(input_file, 'rb') as f:
        encrypted_data = f.read()
    
    decrypted_data = cipher.decrypt(encrypted_data)
    
    with open(output_file, 'wb') as f:
        f.write(decrypted_data) 