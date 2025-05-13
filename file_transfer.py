import os
import socket
import tempfile
import traceback

from PyQt5.QtCore import pyqtSignal, QThread
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from diffie_helman import DiffieHellman


class FileTransferWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_transfer = pyqtSignal()

    def __init__(self, host, port, file_path, is_server=False, save_encrypted=True):
        super().__init__()
        self.host = host
        self.port = port
        self.file_path = file_path
        self.is_server = is_server
        self.dh = DiffieHellman()
        self.save_encrypted = save_encrypted

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
        client_socket = None
        temp_encrypted_path = None

        try:
            # Create server socket
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(1)

            self.status.emit(f"Waiting for connection on {self.host}:{self.port}...")
            client_socket, addr = server_socket.accept()
            self.status.emit(f"Connected to {addr[0]}:{addr[1]}")

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

            # Receive file info
            file_info = client_socket.recv(1024).decode()
            filename, filesize = file_info.split('<SEPARATOR>')
            filesize = int(filesize)

            self.status.emit(f"Receiving file: {filename} ({filesize} bytes)")

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
                encrypted_file_path = os.path.join(self.encrypted_dir, f"received.{filename}.encrypted")
                self.status.emit(f"Saving encrypted copy to {encrypted_file_path}")
                with open(temp_encrypted_path, 'rb') as src, open(encrypted_file_path, 'wb') as dst:
                    dst.write(src.read())

            # Decrypt file
            output_path = os.path.join(self.file_path, filename)
            self.status.emit(f"Decrypting file to {output_path}...")
            self._decrypt_file(temp_encrypted_path, output_path, shared_key)

            # Send acknowledgment
            client_socket.sendall(b"FILE_RECEIVED")
            self.status.emit("File received and decrypted successfully")
            self.finished_transfer.emit()

        except Exception as e:
            raise Exception(f"Server error: {str(e)}")
        finally:
            # Clean up
            if temp_encrypted_path and os.path.exists(temp_encrypted_path):
                os.unlink(temp_encrypted_path)
            if client_socket:
                client_socket.close()
            if server_socket:
                server_socket.close()

    def _handle_client_transfer(self):
        client_socket = None
        temp_encrypted_path = None

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

            # Create temporary file for encrypted data
            temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
            temp_encrypted_path = temp_encrypted.name
            temp_encrypted.close()

            # Encrypt file
            self.status.emit("Encrypting file...")
            self._encrypt_file(self.file_path, temp_encrypted_path, shared_key)

            # Save a copy of the encrypted file if requested
            if self.save_encrypted:
                filename = os.path.basename(self.file_path)
                encrypted_file_path = os.path.join(self.encrypted_dir, f"sent.{filename}.encrypted")
                self.status.emit(f"Saving encrypted copy to {encrypted_file_path}")
                with open(temp_encrypted_path, 'rb') as src, open(encrypted_file_path, 'wb') as dst:
                    dst.write(src.read())

            # Get encrypted file size
            filesize = os.path.getsize(temp_encrypted_path)
            filename = os.path.basename(self.file_path)

            # Send file info
            file_info = f"{filename}<SEPARATOR>{filesize}"
            client_socket.send(file_info.encode())

            # Send encrypted file
            self.status.emit("Sending encrypted file...")
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
            if response != b"FILE_RECEIVED":
                self.status.emit(f"Warning: Unexpected server response: {response}")

            self.status.emit("File sent successfully")
            self.finished_transfer.emit()

        except Exception as e:
            raise Exception(f"Client error: {str(e)}")
        finally:
            # Clean up
            if temp_encrypted_path and os.path.exists(temp_encrypted_path):
                os.unlink(temp_encrypted_path)
            if client_socket:
                client_socket.close()

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
