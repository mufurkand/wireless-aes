import sys
import os
import socket
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QPushButton,
                            QFileDialog, QTextEdit, QMessageBox, QProgressBar)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from encryption import encrypt_file

class FileTransferWorker(QThread):
    """Worker thread for file transfer."""
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_transfer = pyqtSignal()
    
    def __init__(self, host, port, password, file_path):
        super().__init__()
        self.host = host
        self.port = port
        self.password = password
        self.file_path = file_path
    
    def run(self):
        """Run the file transfer"""
        try:
            # Create temporary file for encrypted data
            temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
            temp_encrypted_path = temp_encrypted.name
            temp_encrypted.close()
            
            # Encrypt the file
            self.status.emit("Encrypting file...")
            encrypt_file(self.file_path, temp_encrypted_path, self.password)
            self.status.emit("File encrypted")
            
            # Get encrypted file size
            filesize = os.path.getsize(temp_encrypted_path)
            filename = os.path.basename(self.file_path)
            
            # Create socket and connect to server
            self.status.emit(f"Connecting to {self.host}:{self.port}...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.host, self.port))
            self.status.emit("Connected to server")
            
            # Send file info
            file_info = f"{filename}<SEPARATOR>{filesize}"
            s.send(file_info.encode())
            
            # Send encrypted file
            self.status.emit("Sending encrypted file...")
            bytes_sent = 0
            with open(temp_encrypted_path, 'rb') as f:
                while bytes_sent < filesize:
                    # Read file in chunks
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    
                    # Send chunk
                    s.sendall(chunk)
                    
                    # Update progress
                    bytes_sent += len(chunk)
                    progress_percentage = int(bytes_sent / filesize * 100)
                    self.progress.emit(progress_percentage)
            
            # Wait for server acknowledgment
            response = s.recv(1024)
            if response == b"FILE_RECEIVED":
                self.status.emit("File sent successfully")
            else:
                self.error.emit(f"Unexpected server response: {response.decode()}")
            
            # Clean up
            s.close()
            os.unlink(temp_encrypted_path)
            
            self.finished_transfer.emit()
            
        except Exception as e:
            self.error.emit(str(e))
            
            # Clean up temp file if it exists
            if 'temp_encrypted_path' in locals():
                try:
                    os.unlink(temp_encrypted_path)
                except:
                    pass

class Client(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Transfer - Client")
        self.setMinimumSize(600, 400)
        
        self.selected_file = None
        
        self.init_ui()
    
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Server configuration
        server_layout = QHBoxLayout()
        
        # Host input
        host_label = QLabel("Server IP:")
        self.host_input = QLineEdit("localhost")
        server_layout.addWidget(host_label)
        server_layout.addWidget(self.host_input)
        
        # Port input
        port_label = QLabel("Port:")
        self.port_input = QLineEdit("5000")
        self.port_input.setFixedWidth(100)
        server_layout.addWidget(port_label)
        server_layout.addWidget(self.port_input)
        
        # Password input
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        server_layout.addWidget(password_label)
        server_layout.addWidget(self.password_input)
        
        main_layout.addLayout(server_layout)
        
        # File selection
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        self.file_button = QPushButton("Select File")
        self.file_button.clicked.connect(self.select_file)
        
        file_layout.addWidget(self.file_path_label)
        file_layout.addWidget(self.file_button)
        
        main_layout.addLayout(file_layout)
        
        # Send button
        self.send_button = QPushButton("Send File")
        self.send_button.clicked.connect(self.send_file)
        self.send_button.setEnabled(False)
        main_layout.addWidget(self.send_button)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # Status log
        log_label = QLabel("Log:")
        main_layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def select_file(self):
        """Open file dialog to select a file to send"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File to Send", os.path.expanduser("~")
        )
        
        if file_path:
            self.selected_file = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.send_button.setEnabled(True)
            self.log_message(f"Selected file: {file_path}")
    
    def send_file(self):
        """Initiate file transfer"""
        # Validate inputs
        if not self.validate_inputs():
            return
        
        host = self.host_input.text()
        port = int(self.port_input.text())
        password = self.password_input.text()
        
        # Disable UI elements during transfer
        self.toggle_ui_elements(False)
        
        # Create and start worker thread
        self.worker = FileTransferWorker(host, port, password, self.selected_file)
        self.worker.progress.connect(self.update_progress)
        self.worker.status.connect(self.log_message)
        self.worker.error.connect(self.handle_error)
        self.worker.finished_transfer.connect(self.handle_transfer_finished)
        
        self.worker.start()
    
    def validate_inputs(self):
        """Validate host, port, password and file selection"""
        # Validate host
        host = self.host_input.text()
        if not host:
            QMessageBox.warning(self, "Invalid Host", "Server IP cannot be empty")
            return False
        
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
        
        # Validate file selection
        if not self.selected_file:
            QMessageBox.warning(self, "No File Selected", "Please select a file to send")
            return False
        
        return True
    
    def toggle_ui_elements(self, enabled):
        """Enable or disable UI elements"""
        self.host_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.file_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
    
    def update_progress(self, value):
        """Update progress bar value"""
        self.progress_bar.setValue(value)
    
    def handle_error(self, error_msg):
        """Handle error from worker thread"""
        self.log_message(f"ERROR: {error_msg}")
        QMessageBox.critical(self, "Transfer Error", error_msg)
        self.toggle_ui_elements(True)
    
    def handle_transfer_finished(self):
        """Handle completed file transfer"""
        QMessageBox.information(
            self, 
            "Transfer Complete", 
            f"File '{os.path.basename(self.selected_file)}' has been sent successfully"
        )
        self.progress_bar.setValue(0)
        self.toggle_ui_elements(True)
    
    def log_message(self, message):
        """Add message to log display"""
        self.log_display.append(message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Client()
    window.show()
    sys.exit(app.exec_()) 