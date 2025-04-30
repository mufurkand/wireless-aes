import sys
import os
import socket
import threading
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QPushButton,
                            QFileDialog, QTextEdit, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from encryption import decrypt_file

class WorkerSignals(QObject):
    """Define signals available for the worker thread."""
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    received = pyqtSignal(str, str)  # File path and original filename

class Server(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Transfer - Server")
        self.setMinimumSize(600, 400)
        
        self.server_socket = None
        self.is_running = False
        self.save_directory = os.path.expanduser("~/Downloads")
        
        self.init_ui()
    
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Server configuration
        config_layout = QHBoxLayout()
        
        # Port input
        port_label = QLabel("Port:")
        self.port_input = QLineEdit("5000")
        self.port_input.setFixedWidth(100)
        config_layout.addWidget(port_label)
        config_layout.addWidget(self.port_input)
        
        # Password input
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        config_layout.addWidget(password_label)
        config_layout.addWidget(self.password_input)
        
        # Save directory selection
        config_layout.addStretch()
        self.save_dir_button = QPushButton("Save Directory")
        self.save_dir_button.clicked.connect(self.select_save_directory)
        config_layout.addWidget(self.save_dir_button)
        
        main_layout.addLayout(config_layout)
        
        # Start/Stop server button
        control_layout = QHBoxLayout()
        self.toggle_server_button = QPushButton("Start Server")
        self.toggle_server_button.clicked.connect(self.toggle_server)
        control_layout.addWidget(self.toggle_server_button)
        
        main_layout.addLayout(control_layout)
        
        # Status log
        log_label = QLabel("Server Log:")
        main_layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Status bar
        self.statusBar().showMessage("Server not running")
    
    def select_save_directory(self):
        """Open dialog to select save directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_directory,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.save_directory = directory
            self.log_message(f"Save directory set to: {directory}")
    
    def toggle_server(self):
        """Start or stop the server"""
        if self.is_running:
            self.stop_server()
        else:
            self.start_server()
    
    def start_server(self):
        """Start the server in a separate thread"""
        # Validate inputs
        if not self.validate_inputs():
            return
        
        port = int(self.port_input.text())
        password = self.password_input.text()
        
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('', port))
            self.server_socket.listen(5)
            
            self.is_running = True
            self.toggle_server_button.setText("Stop Server")
            self.statusBar().showMessage(f"Server running on port {port}")
            self.port_input.setEnabled(False)
            self.password_input.setEnabled(False)
            
            self.log_message(f"Server started on port {port}")
            
            # Start listener thread
            self.server_thread = threading.Thread(
                target=self.accept_connections,
                args=(password,),
                daemon=True
            )
            self.server_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Server Error", f"Could not start server: {str(e)}")
            self.log_message(f"Error: {str(e)}")
    
    def stop_server(self):
        """Stop the server"""
        if self.server_socket:
            self.is_running = False
            self.server_socket.close()
            self.server_socket = None
            
            self.toggle_server_button.setText("Start Server")
            self.statusBar().showMessage("Server stopped")
            self.port_input.setEnabled(True)
            self.password_input.setEnabled(True)
            
            self.log_message("Server stopped")
    
    def validate_inputs(self):
        """Validate port and password inputs"""
        # Validate port
        try:
            port = int(self.port_input.text())
            if port < 1024 or port > 65535:
                raise ValueError("Port must be between 1024 and 65535")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Port", str(e))
            return False
        
        # Validate password
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Invalid Password", "Password cannot be empty")
            return False
        
        return True
    
    def accept_connections(self, password):
        """Accept incoming connections"""
        signals = WorkerSignals()
        signals.status.connect(self.log_message)
        signals.error.connect(self.handle_error)
        signals.received.connect(self.handle_received_file)
        
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                signals.status.emit(f"Connection from {address[0]}:{address[1]}")
                
                # Handle client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address, password, signals),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.is_running:  # Only show error if we didn't stop the server intentionally
                    signals.error.emit(f"Connection error: {str(e)}")
    
    def handle_client(self, client_socket, address, password, signals):
        """Handle client connection and file transfer"""
        try:
            # Receive file info
            file_info = client_socket.recv(1024).decode('utf-8')
            filename, filesize = file_info.split('<SEPARATOR>')
            filesize = int(filesize)
            
            signals.status.emit(f"Receiving file: {filename} ({filesize} bytes)")
            
            # Create temporary file for encrypted data
            temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
            temp_encrypted_path = temp_encrypted.name
            temp_encrypted.close()
            
            # Receive and write encrypted file
            bytes_received = 0
            with open(temp_encrypted_path, 'wb') as f:
                while bytes_received < filesize:
                    bytes_to_receive = min(4096, filesize - bytes_received)
                    data = client_socket.recv(bytes_to_receive)
                    if not data:
                        break
                    f.write(data)
                    bytes_received += len(data)
            
            # Acknowledge receipt
            client_socket.send(b"FILE_RECEIVED")
            
            # Decrypt the file
            output_path = os.path.join(self.save_directory, filename)
            decrypt_file(temp_encrypted_path, output_path, password)
            
            # Clean up temp file
            os.unlink(temp_encrypted_path)
            
            signals.status.emit(f"File received and decrypted: {filename}")
            signals.received.emit(output_path, filename)
            
        except Exception as e:
            signals.error.emit(f"Error handling client {address[0]}: {str(e)}")
        finally:
            client_socket.close()
    
    def handle_received_file(self, file_path, filename):
        """Handle received and decrypted file"""
        QMessageBox.information(
            self, 
            "File Received", 
            f"File '{filename}' has been received and saved to {file_path}"
        )
    
    def handle_error(self, error_msg):
        """Handle error from worker thread"""
        self.log_message(f"ERROR: {error_msg}")
        # Show error message box if needed
        # QMessageBox.critical(self, "Error", error_msg)
    
    def log_message(self, message):
        """Add message to log display"""
        self.log_display.append(message)
    
    def closeEvent(self, event):
        """Clean up on window close"""
        if self.server_socket:
            self.stop_server()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Server()
    window.show()
    sys.exit(app.exec_()) 