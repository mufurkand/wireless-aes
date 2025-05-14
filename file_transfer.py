import os
import socket
import tempfile
import traceback
import zipfile
import shutil
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QThread
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from diffie_helman import DiffieHellman


class FileTransferWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_transfer = pyqtSignal()

    def __init__(self, host, port, file_paths, is_server=False, save_encrypted=True):
        super().__init__()
        self.host = host
        self.port = port
        # Can now be a list of paths or a single path (for backward compatibility)
        self.file_paths = file_paths if isinstance(file_paths, list) else [file_paths]
        self.is_server = is_server
        self.dh = DiffieHellman()
        self.save_encrypted = save_encrypted
        self.running = True  # Flag to control continuous server mode

        # Create encrypted directory if it doesn't exist
        self.encrypted_dir = os.path.join(os.getcwd(), "encrypted")
        if not os.path.exists(self.encrypted_dir):
            os.makedirs(self.encrypted_dir)

    def run(self):
        try:
            if self.is_server:
                self._handle_server_transfer()
            else:
                self._handle_client_transfer()
        except Exception as e:
            traceback.print_exc()  # Print detailed error
            self.error.emit(str(e))

    def _handle_server_transfer(self):
        server_socket = None
        
        try:
            # Create server socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.settimeout(1.0)  # Add timeout to allow checking self.running
            server_socket.listen(1)
            
            self.status.emit(f"Server listening on {self.host}:{self.port}...")
            
            # Loop to continuously accept connections
            while self.running:
                try:
                    # Accept connection with timeout to check self.running periodically
                    client_socket, addr = server_socket.accept()
                    self.status.emit(f"Connected to {addr[0]}:{addr[1]}")
                    
                    # Handle this connection
                    self._handle_client_connection(client_socket)
                    
                except socket.timeout:
                    # This is just to check if we should continue running
                    continue
                except Exception as e:
                    if self.running:  # Only report errors if we're still supposed to be running
                        self.status.emit(f"Connection error: {str(e)}")
                        # Continue to accept next connection
            
            self.status.emit("Server stopped")
                
        except Exception as e:
            if self.running:  # Only report errors if we're still supposed to be running
                raise Exception(f"Server error: {str(e)}")
        finally:
            if server_socket:
                server_socket.close()
                
    def _handle_client_connection(self, client_socket):
        temp_encrypted_path = None
        temp_zip_path = None
        
        try:
            # Exchange public keys
            self.status.emit("Exchanging encryption keys...")
            client_socket.sendall(self.dh.get_public_key_bytes())

            # The server sends first, then receives
            client_public_key_data = b""
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                client_public_key_data += data
                if b"-----END PUBLIC KEY-----" in client_public_key_data:
                    break

            if not client_public_key_data:
                raise Exception("Failed to receive client public key")

            self.status.emit("Computing shared encryption key...")
            shared_key = self.dh.get_shared_key(client_public_key_data)
            self.status.emit("Secure connection established")

            # Receive transfer info
            transfer_info = client_socket.recv(2048).decode()
            parts = transfer_info.split('<SEPARATOR>')

            if len(parts) < 2:
                raise Exception("Invalid transfer information received")

            archive_name = parts[0]
            filesize = int(parts[1])
            num_items = int(parts[2]) if len(parts) > 2 else 1

            self.status.emit(f"Receiving archive: {archive_name} ({filesize} bytes) containing {num_items} items")

            # Create temporary file for encrypted data
            temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
            temp_encrypted_path = temp_encrypted.name
            temp_encrypted.close()

            # Receive encrypted file
            bytes_received = 0
            with open(temp_encrypted_path, 'wb') as f:
                while bytes_received < filesize:
                    bytes_to_receive = min(4096, filesize - bytes_received)
                    data = client_socket.recv(bytes_to_receive)
                    if not data:
                        break
                    f.write(data)
                    bytes_received += len(data)
                    progress = int(bytes_received / filesize * 100)
                    self.progress.emit(progress)

            # Save a copy of the encrypted file if requested
            if self.save_encrypted:
                encrypted_file_path = os.path.join(self.encrypted_dir, f"received.{archive_name}.encrypted")
                self.status.emit(f"Saving encrypted copy to {encrypted_file_path}")
                with open(temp_encrypted_path, 'rb') as src, open(encrypted_file_path, 'wb') as dst:
                    dst.write(src.read())

            # Create temporary file for decrypted archive
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip_path = temp_zip.name
            temp_zip.close()

            # Decrypt file
            self.status.emit(f"Decrypting received archive...")
            self._decrypt_file(temp_encrypted_path, temp_zip_path, shared_key)

            # Extract archive to destination folder
            output_dir = self.file_paths[0]  # First path is the destination directory
            self.status.emit(f"Extracting files to {output_dir}...")

            # Extract the zip file
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                # Get total size for progress reporting
                total_size = sum(file.file_size for file in zip_ref.infolist())
                extracted_size = 0

                for file in zip_ref.infolist():
                    zip_ref.extract(file, output_dir)
                    extracted_size += file.file_size
                    self.progress.emit(int(extracted_size / total_size * 100))

            # Send acknowledgment
            client_socket.sendall(b"FILES_RECEIVED")
            self.status.emit(f"Successfully received and extracted {num_items} items")
            self.finished_transfer.emit()

        except Exception as e:
            self.status.emit(f"Error processing connection: {str(e)}")
        finally:
            # Clean up
            if temp_encrypted_path and os.path.exists(temp_encrypted_path):
                os.unlink(temp_encrypted_path)
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
            if client_socket:
                client_socket.close()
                
    def terminate(self):
        self.running = False
        super().terminate()

    def _handle_client_transfer(self):
        client_socket = None
        temp_encrypted_path = None
        temp_zip_path = None

        try:
            # Connect to server
            self.status.emit(f"Connecting to {self.host}:{self.port}...")
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.host, self.port))
            self.status.emit("Connected to server")

            # Exchange public keys
            self.status.emit("Exchanging encryption keys...")

            # First receive the server's public key
            server_public_key_data = b""
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                server_public_key_data += data
                if b"-----END PUBLIC KEY-----" in server_public_key_data:
                    break

            if not server_public_key_data:
                raise Exception("Failed to receive server public key")

            # Then send our public key
            client_socket.sendall(self.dh.get_public_key_bytes())

            self.status.emit("Computing shared encryption key...")
            shared_key = self.dh.get_shared_key(server_public_key_data)
            self.status.emit("Secure connection established")

            # Create a temporary ZIP archive to bundle all files and folders
            self.status.emit("Creating archive of selected items...")
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            temp_zip_path = temp_zip.name
            temp_zip.close()

            total_files = sum(1 for _ in self._count_files_in_paths(self.file_paths))
            files_processed = 0

            # Create zip archive of all selected files and folders
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for path in self.file_paths:
                    self._add_to_zip(zipf, path, "", files_processed, total_files)

            # Create temporary file for encrypted data
            temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
            temp_encrypted_path = temp_encrypted.name
            temp_encrypted.close()

            # Encrypt the zip file
            self.status.emit("Encrypting archive...")
            self._encrypt_file(temp_zip_path, temp_encrypted_path, shared_key)

            # Save a copy of the encrypted file if requested
            if self.save_encrypted:
                archive_name = "secure_transfer_archive.zip"
                encrypted_file_path = os.path.join(self.encrypted_dir, f"sent.{archive_name}.encrypted")
                self.status.emit(f"Saving encrypted copy to {encrypted_file_path}")
                with open(temp_encrypted_path, 'rb') as src, open(encrypted_file_path, 'wb') as dst:
                    dst.write(src.read())

            # Get encrypted file size
            filesize = os.path.getsize(temp_encrypted_path)

            # Create a descriptive archive name
            if len(self.file_paths) == 1:
                base_name = os.path.basename(self.file_paths[0])
                if os.path.isdir(self.file_paths[0]):
                    archive_name = f"{base_name}_folder.zip"
                else:
                    archive_name = f"{base_name}.zip"
            else:
                archive_name = "multiple_items.zip"

            # Send transfer info (name, size, number of items)
            transfer_info = f"{archive_name}<SEPARATOR>{filesize}<SEPARATOR>{len(self.file_paths)}"
            client_socket.send(transfer_info.encode())

            # Send encrypted archive
            self.status.emit("Sending encrypted archive...")
            bytes_sent = 0
            with open(temp_encrypted_path, 'rb') as f:
                while bytes_sent < filesize:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    client_socket.sendall(chunk)
                    bytes_sent += len(chunk)
                    progress = int(bytes_sent / filesize * 100)
                    self.progress.emit(progress)

            # Wait for acknowledgment
            response = client_socket.recv(1024)
            if response != b"FILES_RECEIVED":
                self.status.emit(f"Warning: Unexpected server response: {response}")

            self.status.emit(f"Successfully sent {len(self.file_paths)} items")
            self.finished_transfer.emit()

        except Exception as e:
            raise Exception(f"Client error: {str(e)}")
        finally:
            # Clean up
            if temp_encrypted_path and os.path.exists(temp_encrypted_path):
                os.unlink(temp_encrypted_path)
            if temp_zip_path and os.path.exists(temp_zip_path):
                os.unlink(temp_zip_path)
            if client_socket:
                client_socket.close()

    def _add_to_zip(self, zipf, path, arcname, files_processed, total_files):
        """Add file or folder to zip archive with progress tracking"""
        if os.path.isfile(path):
            # If it's a file, add it directly
            if arcname:
                zipf.write(path, arcname)
            else:
                zipf.write(path, os.path.basename(path))
            files_processed += 1
            self.progress.emit(int(files_processed / total_files * 100))
        else:
            # If it's a directory, add all its contents
            base_name = os.path.basename(path)
            for root, dirs, files in os.walk(path):
                # Calculate relative path from the source directory
                if arcname:
                    rel_dir = os.path.join(arcname, os.path.relpath(root, os.path.dirname(path)))
                else:
                    rel_dir = os.path.relpath(root, os.path.dirname(path))

                # Add empty directories
                if not files and not dirs:
                    zipf.writestr(f"{rel_dir}/", "")

                # Add files
                for file in files:
                    file_path = os.path.join(root, file)
                    if arcname:
                        arc_file = os.path.join(arcname, os.path.relpath(file_path, os.path.dirname(path)))
                    else:
                        arc_file = os.path.relpath(file_path, os.path.dirname(path))
                    zipf.write(file_path, arc_file)
                    files_processed += 1
                    self.progress.emit(int(files_processed / total_files * 100))

    def _count_files_in_paths(self, paths):
        """Generator to count total files in all paths"""
        for path in paths:
            if os.path.isfile(path):
                yield 1
            else:
                for root, _, files in os.walk(path):
                    for _ in files:
                        yield 1

    def _encrypt_file(self, input_file, output_file, key):
        # Generate IV
        iv = os.urandom(16)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),  # Key is already 32 bytes from HKDF
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Read and encrypt file
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            # Write IV
            f_out.write(iv)

            # Read file in chunks and encrypt
            buffer = b""
            while True:
                chunk = f_in.read(4096)
                if not chunk and not buffer:
                    break

                buffer += chunk

                # Process complete blocks, keeping any remainder for the next iteration
                blocks, remainder = divmod(len(buffer), 16)
                if not chunk:  # Last chunk needs padding
                    padding_length = 16 - remainder
                    buffer += bytes([padding_length]) * padding_length
                    remainder = 0

                if blocks > 0 or not chunk:
                    to_encrypt = buffer[:-remainder] if remainder else buffer
                    encrypted_chunk = encryptor.update(to_encrypt)
                    f_out.write(encrypted_chunk)
                    buffer = buffer[-remainder:] if remainder else b""

            # Write final block
            final = encryptor.finalize()
            if final:
                f_out.write(final)

    def _decrypt_file(self, input_file, output_file, key):
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            # Read IV
            iv = f_in.read(16)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),  # Key is already 32 bytes from HKDF
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # Read and decrypt in chunks, but keep the last chunk separate
            chunks = []
            while True:
                chunk = f_in.read(4096)
                if not chunk:
                    break
                chunks.append(chunk)

            # Process all but the last chunk
            for i in range(len(chunks) - 1):
                decrypted_chunk = decryptor.update(chunks[i])
                f_out.write(decrypted_chunk)

            # Process the last chunk
            if chunks:
                last_chunk = chunks[-1]
                decrypted_chunk = decryptor.update(last_chunk)
                final_chunk = decryptor.finalize()

                # Combine the last decrypted chunk with the final chunk
                final_data = decrypted_chunk + final_chunk

                # Remove padding
                if final_data:
                    padding_length = final_data[-1]
                    if padding_length < 16 and all(b == padding_length for b in final_data[-padding_length:]):
                        final_data = final_data[:-padding_length]

                f_out.write(final_data)
            else:
                # If there were no chunks, still finalize
                f_out.write(decryptor.finalize())