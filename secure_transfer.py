import sys
import os
import socket
import threading
import tempfile
import traceback
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QPushButton,
                            QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                            QTabWidget, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from cryptography.hazmat.primitives.asymmetric import dh
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64

# Fixed DH parameters - Both sides must use the same parameters
# These are 2048-bit RFC 3526 MODP Group 14 parameters
P = int(
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
    "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
    "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
    "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
    "670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9"
    "DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AACAA68FFFFFFFFFFFFFFFF", 16
)
G = 2

class DiffieHellman:
    def __init__(self):
        # Use fixed parameters instead of generating new ones
        self.parameters = dh.DHParameterNumbers(p=P, g=G, q=None).parameters(default_backend())
        # Generate private key with these parameters
        self.private_key = self.parameters.generate_private_key()
        # Get public key
        self.public_key = self.private_key.public_key()
    
    def get_public_key_bytes(self):
        try:
            return self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        except Exception as e:
            raise Exception(f"Error serializing public key: {str(e)}")
    
    def get_shared_key(self, peer_public_key_bytes):
        try:
            peer_public_key = serialization.load_pem_public_key(
                peer_public_key_bytes,
                backend=default_backend()
            )
            
            # Get the shared key
            shared_secret = self.private_key.exchange(peer_public_key)
            
            # Derive a suitable encryption key using HKDF
            derived_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 32 bytes for AES-256
                salt=None,
                info=b'handshake data',
                backend=default_backend()
            ).derive(shared_secret)
            
            return derived_key
            
        except Exception as e:
            traceback.print_exc()
            raise Exception(f"Error computing shared key: {str(e)}")

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

class SecureTransferApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Transfer")
        self.setMinimumSize(800, 600)
        
        self.selected_file = None
        self.init_ui()
    
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Create tab widget
        tab_widget = QTabWidget()
        
        # Create Send and Receive tabs
        send_tab = QWidget()
        receive_tab = QWidget()
        
        tab_widget.addTab(send_tab, "Send File")
        tab_widget.addTab(receive_tab, "Receive File")
        
        # Setup Send tab
        send_layout = QVBoxLayout()
        
        # Server configuration
        server_layout = QHBoxLayout()
        
        host_label = QLabel("Server IP:")
        self.host_input = QLineEdit("localhost")
        server_layout.addWidget(host_label)
        server_layout.addWidget(self.host_input)
        
        port_label = QLabel("Port:")
        self.port_input = QLineEdit("5000")
        self.port_input.setFixedWidth(100)
        server_layout.addWidget(port_label)
        server_layout.addWidget(self.port_input)
        
        send_layout.addLayout(server_layout)
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        self.file_button = QPushButton("Select File")
        self.file_button.clicked.connect(self.select_file)
        
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(self.file_button)
        
        send_layout.addLayout(file_layout)
        
        # Save encrypted checkbox
        save_encrypted_layout = QHBoxLayout()
        self.save_encrypted_cb = QCheckBox("Save encrypted version")
        self.save_encrypted_cb.setChecked(True)
        save_encrypted_layout.addWidget(self.save_encrypted_cb)
        save_encrypted_layout.addStretch()
        
        send_layout.addLayout(save_encrypted_layout)
        
        # Send button
        self.send_button = QPushButton("Send File")
        self.send_button.clicked.connect(self.send_file)
        self.send_button.setEnabled(False)
        send_layout.addWidget(self.send_button)
        
        # Progress bar
        self.send_progress = QProgressBar()
        self.send_progress.setRange(0, 100)
        self.send_progress.setValue(0)
        send_layout.addWidget(self.send_progress)
        
        # Status log
        log_label = QLabel("Log:")
        send_layout.addWidget(log_label)

        self.send_log = QTextEdit()
        self.send_log.setReadOnly(True)
        send_layout.addWidget(self.send_log)
        
        send_tab.setLayout(send_layout)

        # Clear log button - Send tab
        self.clear_send_log_button = QPushButton("Clear Log")
        self.clear_send_log_button.clicked.connect(self.clear_send_log)
        send_layout.addWidget(self.clear_send_log_button)

        clear_send_layout = QHBoxLayout()
        clear_send_layout.addStretch()
        clear_send_layout.addWidget(self.clear_send_log_button)
        send_layout.addLayout(clear_send_layout)

        # Setup Receive tab
        receive_layout = QVBoxLayout()

        # Server configuration
        receive_config_layout = QHBoxLayout()
        
        receive_host_label = QLabel("Listen IP:")
        self.receive_host_input = QLineEdit("0.0.0.0")
        receive_config_layout.addWidget(receive_host_label)
        receive_config_layout.addWidget(self.receive_host_input)
        
        receive_port_label = QLabel("Port:")
        self.receive_port_input = QLineEdit("5000")
        self.receive_port_input.setFixedWidth(100)
        receive_config_layout.addWidget(receive_port_label)
        receive_config_layout.addWidget(self.receive_port_input)
        
        receive_layout.addLayout(receive_config_layout)
        
        # Save directory selection
        save_dir_layout = QHBoxLayout()
        self.save_dir_label = QLabel(os.path.expanduser("~/Downloads"))
        self.save_dir_button = QPushButton("Select Save Directory")
        self.save_dir_button.clicked.connect(self.select_save_directory)
        
        save_dir_layout.addWidget(self.save_dir_label)
        save_dir_layout.addWidget(self.save_dir_button)
        
        receive_layout.addLayout(save_dir_layout)
        
        # Save encrypted checkbox for receive tab
        receive_encrypted_layout = QHBoxLayout()
        self.receive_encrypted_cb = QCheckBox("Save encrypted version")
        self.receive_encrypted_cb.setChecked(True)
        receive_encrypted_layout.addWidget(self.receive_encrypted_cb)
        receive_encrypted_layout.addStretch()
        
        receive_layout.addLayout(receive_encrypted_layout)
        
        # Receive button
        self.receive_button = QPushButton("Start Receiving")
        self.receive_button.clicked.connect(self.start_receiving)
        receive_layout.addWidget(self.receive_button)
        
        # Progress bar
        self.receive_progress = QProgressBar()
        self.receive_progress.setRange(0, 100)
        self.receive_progress.setValue(0)
        receive_layout.addWidget(self.receive_progress)
        
        # Status log
        receive_log_label = QLabel("Log:")
        receive_layout.addWidget(receive_log_label)
        
        self.receive_log = QTextEdit()
        self.receive_log.setReadOnly(True)
        receive_layout.addWidget(self.receive_log)

        # Clear log button - Receive tab
        self.clear_receive_log_button = QPushButton("Clear Log")
        self.clear_receive_log_button.clicked.connect(self.clear_receive_log)
        receive_layout.addWidget(self.clear_receive_log_button)
        receive_tab.setLayout(receive_layout)

        clear_receive_layout = QHBoxLayout()
        clear_receive_layout.addStretch()
        clear_receive_layout.addWidget(self.clear_receive_log_button)
        receive_layout.addLayout(clear_receive_layout)

        # Add tab widget to main layout
        main_layout.addWidget(tab_widget)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File to Send", os.path.expanduser("~")
        )
        
        if file_path:
            self.selected_file = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.send_button.setEnabled(True)
            self.log_message("Send", f"Selected file: {file_path}")
    
    def select_save_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir_label.text(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.save_dir_label.setText(directory)
            self.log_message("Receive", f"Save directory set to: {directory}")
    
    def send_file(self):
        if not self.validate_send_inputs():
            return
        
        host = self.host_input.text()
        port = int(self.port_input.text())
        save_encrypted = self.save_encrypted_cb.isChecked()
        
        self.toggle_send_ui(False)
        
        self.worker = FileTransferWorker(host, port, self.selected_file, save_encrypted=save_encrypted)
        self.worker.progress.connect(self.update_send_progress)
        self.worker.status.connect(lambda msg: self.log_message("Send", msg))
        self.worker.error.connect(self.handle_send_error)
        self.worker.finished_transfer.connect(self.handle_send_finished)
        
        self.worker.start()
    
    def start_receiving(self):
        if not self.validate_receive_inputs():
            return
        
        host = self.receive_host_input.text()
        port = int(self.receive_port_input.text())
        save_encrypted = self.receive_encrypted_cb.isChecked()
        
        self.toggle_receive_ui(False)
        
        self.worker = FileTransferWorker(host, port, self.save_dir_label.text(), 
                                        is_server=True, save_encrypted=save_encrypted)
        self.worker.progress.connect(self.update_receive_progress)
        self.worker.status.connect(lambda msg: self.log_message("Receive", msg))
        self.worker.error.connect(self.handle_receive_error)
        self.worker.finished_transfer.connect(self.handle_receive_finished)
        
        self.worker.start()
    
    def validate_send_inputs(self):
        host = self.host_input.text()
        if not host:
            QMessageBox.warning(self, "Invalid Host", "Server IP cannot be empty")
            return False
        
        try:
            port = int(self.port_input.text())
            if port < 1024 or port > 65535:
                raise ValueError("Port must be between 1024 and 65535")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Port", str(e))
            return False
        
        if not self.selected_file:
            QMessageBox.warning(self, "No File Selected", "Please select a file to send")
            return False
        
        return True
    
    def validate_receive_inputs(self):
        host = self.receive_host_input.text()
        if not host:
            QMessageBox.warning(self, "Invalid Host", "Listen IP cannot be empty")
            return False
        
        try:
            port = int(self.receive_port_input.text())
            if port < 1024 or port > 65535:
                raise ValueError("Port must be between 1024 and 65535")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Port", str(e))
            return False
        
        return True
    
    def toggle_send_ui(self, enabled):
        self.host_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.file_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.save_encrypted_cb.setEnabled(enabled)
    
    def toggle_receive_ui(self, enabled):
        self.receive_host_input.setEnabled(enabled)
        self.receive_port_input.setEnabled(enabled)
        self.save_dir_button.setEnabled(enabled)
        self.receive_button.setEnabled(enabled)
        self.receive_encrypted_cb.setEnabled(enabled)
    
    def update_send_progress(self, value):
        self.send_progress.setValue(value)
    
    def update_receive_progress(self, value):
        self.receive_progress.setValue(value)
    
    def handle_send_error(self, error_msg):
        self.log_message("Send", f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Send Error", error_msg)
        self.toggle_send_ui(True)
    
    def handle_receive_error(self, error_msg):
        self.log_message("Receive", f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Receive Error", error_msg)
        self.toggle_receive_ui(True)
    
    def handle_send_finished(self):
        QMessageBox.information(
            self, 
            "Send Complete", 
            f"File '{os.path.basename(self.selected_file)}' has been sent successfully"
        )
        self.send_progress.setValue(0)
        self.toggle_send_ui(True)
    
    def handle_receive_finished(self):
        QMessageBox.information(
            self, 
            "Receive Complete", 
            "File has been received and decrypted successfully"
        )
        self.receive_progress.setValue(0)
        self.toggle_receive_ui(True)
    
    def log_message(self, tab, message):
        if tab == "Send":
            self.send_log.append(message)
        else:
            self.receive_log.append(message)

    def clear_send_log(self):
        self.send_log.clear()
        self.log_message("Send", "Log cleared")

    def clear_receive_log(self):
        self.receive_log.clear()
        self.log_message("Receive", "Log cleared")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SecureTransferApp()
    window.show()
    sys.exit(app.exec_()) 