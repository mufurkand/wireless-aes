#!/usr/bin/env python
"""
Demo script for Secure File Transfer application.
This script tests the encryption and decryption functionality.
"""
import os
import tempfile
from encryption import encrypt_file, decrypt_file

def test_encryption():
    """Test the encryption and decryption functions."""
    # Create a temporary file with test content
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(b"This is a test message for encryption and decryption!")
        original_file = temp_file.name
    
    # Create temporary files for encrypted and decrypted content
    encrypted_file = original_file + ".encrypted"
    decrypted_file = original_file + ".decrypted"
    
    # Test password
    password = "test-password-123"
    
    try:
        print("Testing encryption module...")
        
        # Encrypt the file
        print(f"Encrypting {original_file} to {encrypted_file}")
        encrypt_file(original_file, encrypted_file, password)
        
        # Decrypt the file
        print(f"Decrypting {encrypted_file} to {decrypted_file}")
        decrypt_file(encrypted_file, decrypted_file, password)
        
        # Compare original and decrypted content
        with open(original_file, 'rb') as f1, open(decrypted_file, 'rb') as f2:
            original_content = f1.read()
            decrypted_content = f2.read()
        
        if original_content == decrypted_content:
            print("Success! Encryption and decryption work correctly.")
            print("Original content:", original_content.decode())
            print("Decrypted content:", decrypted_content.decode())
        else:
            print("Error! Decrypted content does not match original.")
    
    finally:
        # Clean up temporary files
        for file_path in [original_file, encrypted_file, decrypted_file]:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Removed temporary file: {file_path}")

def main():
    """Main function."""
    print("=" * 50)
    print("Secure File Transfer Demo")
    print("=" * 50)
    
    # Test encryption
    test_encryption()
    
    print("\n" + "=" * 50)
    print("How to run the application:")
    print("=" * 50)
    print("1. Run the server:")
    print("   python server.py")
    print("\n2. Run the client:")
    print("   python client.py")
    print("\n3. In the client:")
    print("   - Enter server IP address, port, and password (matching server)")
    print("   - Select a file to transfer")
    print("   - Click 'Send File'")
    print("=" * 50)

if __name__ == "__main__":
    main() 