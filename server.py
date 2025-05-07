import sys
import os
import socket
import threading
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QPushButton,
                            QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                            QFrame, QStyleFactory, QCheckBox, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QColor, QPalette
from encryption import decrypt_file

class WorkerSignals(QObject):
    """Define signals available for the worker thread."""
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    received = pyqtSignal(str, str)  # File path and original filename
    progress = pyqtSignal(int)  # Progress percentage

class Server(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Transfer - Server")
        self.setMinimumSize(700, 500)
        
        self.server_socket = None
        self.is_running = False
        self.save_directory = os.path.expanduser("~/Downloads")
        self.dark_mode = False
        
        self.init_ui()
    
    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Server configuration group
        server_frame = QFrame()
        server_frame.setFrameShape(QFrame.StyledPanel)
        server_layout = QVBoxLayout(server_frame)
        
        config_label = QLabel("Server Configuration")
        config_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        server_layout.addWidget(config_label)
        
        # Server input fields in a grid
        server_fields = QHBoxLayout()
        
        # Port input
        port_layout = QVBoxLayout()
        port_label = QLabel("Port:")
        self.port_input = QLineEdit("5000")
        self.port_input.setPlaceholderText("e.g. 5000")
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        server_fields.addLayout(port_layout, 1)
        
        # Password input
        password_layout = QVBoxLayout()
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter password")
        
        # Show/hide password checkbox
        self.show_password = QCheckBox("Show password")
        self.show_password.toggled.connect(self.toggle_password_visibility)
        
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        password_layout.addWidget(self.show_password)
        server_fields.addLayout(password_layout, 2)
        
        # Save directory selection
        save_dir_layout = QVBoxLayout()
        save_dir_label = QLabel("Save Directory:")
        self.save_dir_display = QLineEdit(self.save_directory)
        self.save_dir_display.setReadOnly(True)
        
        save_dir_button_layout = QHBoxLayout()
        self.save_dir_button = QPushButton("Browse...")
        self.save_dir_button.clicked.connect(self.select_save_directory)
        save_dir_button_layout.addWidget(self.save_dir_display)
        save_dir_button_layout.addWidget(self.save_dir_button)
        
        save_dir_layout.addWidget(save_dir_label)
        save_dir_layout.addLayout(save_dir_button_layout)
        server_fields.addLayout(save_dir_layout, 3)
        
        server_layout.addLayout(server_fields)
        main_layout.addWidget(server_frame)
        
        # Server control group
        control_frame = QFrame()
        control_frame.setFrameShape(QFrame.StyledPanel)
        control_layout = QVBoxLayout(control_frame)
        
        control_header = QLabel("Server Control")
        control_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        control_layout.addWidget(control_header)
        
        # Start/Stop button
        button_layout = QHBoxLayout()
        self.toggle_server_button = QPushButton("Start Server")
        self.toggle_server_button.setMinimumHeight(40)
        self.toggle_server_button.clicked.connect(self.toggle_server)
        button_layout.addWidget(self.toggle_server_button)
        
        # Status indicator
        self.status_label = QLabel("Server Status: Stopped")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        button_layout.addWidget(self.status_label)
        
        # Dark mode toggle
        self.dark_mode_toggle = QCheckBox("Dark Mode")
        self.dark_mode_toggle.toggled.connect(self.toggle_dark_mode)
        button_layout.addWidget(self.dark_mode_toggle)
        
        control_layout.addLayout(button_layout)
        main_layout.addWidget(control_frame)
        
        # Activity and connection information
        activity_frame = QFrame()
        activity_frame.setFrameShape(QFrame.StyledPanel)
        activity_layout = QVBoxLayout(activity_frame)
        
        activity_header = QLabel("Server Activity")
        activity_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        activity_layout.addWidget(activity_header)
        
        # Recent files received
        self.recent_files_label = QLabel("No files received yet")
        activity_layout.addWidget(self.recent_files_label)
        
        # Progress bar for current transfer
        progress_header = QLabel("Transfer Progress")
        progress_header.setStyleSheet("font-weight: bold;")
        activity_layout.addWidget(progress_header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v / %m")
        self.progress_bar.setMinimumHeight(25)
        activity_layout.addWidget(self.progress_bar)
        
        main_layout.addWidget(activity_frame)
        
        # Log display group
        log_frame = QFrame()
        log_frame.setFrameShape(QFrame.StyledPanel)
        log_layout = QVBoxLayout(log_frame)
        
        log_header = QLabel("Server Log")
        log_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        log_layout.addWidget(log_header)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # Clear log button
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_log)
        log_layout.addWidget(self.clear_log_button)
        
        main_layout.addWidget(log_frame)
        
        # Set main layout
        main_widget.setLayout(main_layout)
        
        # Add a right-side widget to show connected clients (can be expanded later)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(main_widget)
        
        self.setCentralWidget(splitter)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Apply initial styles
        self.apply_styles()
    
    def select_save_directory(self):
        """Open dialog to select save directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_directory,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.save_directory = directory
            self.save_dir_display.setText(directory)
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
            self.status_label.setText("Server Status: Running")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            self.statusBar().showMessage(f"Server running on port {port}")
            
            # Disable inputs while server is running
            self.port_input.setEnabled(False)
            self.password_input.setEnabled(False)
            self.show_password.setEnabled(False)
            self.save_dir_button.setEnabled(False)
            
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
            self.status_label.setText("Server Status: Stopped")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self.statusBar().showMessage("Server stopped")
            
            # Re-enable inputs
            self.port_input.setEnabled(True)
            self.password_input.setEnabled(True)
            self.show_password.setEnabled(True)
            self.save_dir_button.setEnabled(True)
            
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
        
        # Validate save directory
        if not os.path.isdir(self.save_directory):
            QMessageBox.warning(self, "Invalid Directory", "Selected save directory does not exist")
            return False
        
        return True
    
    def accept_connections(self, password):
        """Accept incoming connections"""
        signals = WorkerSignals()
        signals.status.connect(self.log_message)
        signals.error.connect(self.handle_error)
        signals.received.connect(self.handle_received_file)
        signals.progress.connect(self.update_progress)
        
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
                    
                    # Update progress
                    progress_percentage = int(bytes_received / filesize * 100)
                    signals.progress.emit(progress_percentage)
            
            # Acknowledge receipt
            client_socket.send(b"FILE_RECEIVED")
            
            # Decrypt the file
            output_path = os.path.join(self.save_directory, filename)
            signals.status.emit(f"Decrypting file: {filename}")
            decrypt_file(temp_encrypted_path, output_path, password)
            
            # Clean up temp file
            os.unlink(temp_encrypted_path)
            
            signals.status.emit(f"File received and decrypted: {filename}")
            signals.received.emit(output_path, filename)
            
        except Exception as e:
            signals.error.emit(f"Error handling client {address[0]}: {str(e)}")
        finally:
            client_socket.close()
    
    def update_progress(self, value):
        """Update progress bar value"""
        self.progress_bar.setValue(value)
        
        # Update progress bar color based on progress
        if value < 30:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #ff9800; }")
        elif value < 70:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2196f3; }")
        else:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4caf50; }")
    
    def handle_received_file(self, file_path, filename):
        """Handle received and decrypted file"""
        QMessageBox.information(
            self, 
            "File Received", 
            f"File '{filename}' has been received and saved to {file_path}"
        )
        
        # Update recent files label
        self.recent_files_label.setText(f"Last received: {filename} - Saved to: {file_path}")
        
        # Reset progress bar
        self.progress_bar.setValue(0)
    
    def handle_error(self, error_msg):
        """Handle error from worker thread"""
        self.log_message(f"ERROR: {error_msg}")
        # Show error message box if needed
        QMessageBox.critical(self, "Error", error_msg)
    
    def log_message(self, message):
        """Add message to log display"""
        self.log_display.append(message)
    
    def clear_log(self):
        """Clear the log display"""
        self.log_display.clear()
    
    def toggle_password_visibility(self, checked):
        """Toggle password visibility"""
        if checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
    
    def toggle_dark_mode(self, checked):
        """Toggle dark mode"""
        self.dark_mode = checked
        self.apply_styles()
    
    def apply_styles(self):
        """Apply styling based on dark mode setting"""
        if self.dark_mode:
            # Dark mode palette
            palette = QPalette()
            background_color = QColor(45, 45, 45)
            text_color = QColor(255, 255, 255)
            
            palette.setColor(QPalette.Window, background_color)
            palette.setColor(QPalette.WindowText, text_color)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, background_color)
            palette.setColor(QPalette.ToolTipBase, background_color)
            palette.setColor(QPalette.ToolTipText, text_color)
            palette.setColor(QPalette.Text, text_color)
            palette.setColor(QPalette.Button, background_color)
            palette.setColor(QPalette.ButtonText, text_color)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            
            self.setPalette(palette)
            self.setStyleSheet("""
                QFrame { border: 1px solid #555; border-radius: 3px; }
                QProgressBar { border: 1px solid #555; border-radius: 3px; text-align: center; }
                QProgressBar::chunk { border-radius: 3px; }
                QPushButton { 
                    background-color: #2a82da; 
                    border: none; 
                    color: white; 
                    padding: 5px; 
                    border-radius: 3px; 
                }
                QPushButton:hover { background-color: #3a92ea; }
                QPushButton:disabled { background-color: #555; color: #888; }
                QLineEdit, QTextEdit { 
                    background-color: #333; 
                    border: 1px solid #555;
                    color: white;
                    padding: 3px;
                    border-radius: 3px;
                }
            """)
        else:
            # Light mode - reset to default
            self.setPalette(self.style().standardPalette())
            self.setStyleSheet("""
                QFrame { border: 1px solid #ccc; border-radius: 3px; }
                QProgressBar { border: 1px solid #ccc; border-radius: 3px; text-align: center; }
                QProgressBar::chunk { border-radius: 3px; }
                QPushButton { 
                    background-color: #0d6efd; 
                    border: none; 
                    color: white; 
                    padding: 5px; 
                    border-radius: 3px; 
                }
                QPushButton:hover { background-color: #0b5ed7; }
                QPushButton:disabled { background-color: #cccccc; color: #666666; }
                QLineEdit, QTextEdit { 
                    border: 1px solid #ccc;
                    padding: 3px;
                    border-radius: 3px;
                }
            """)
    
    def closeEvent(self, event):
        """Clean up on window close"""
        if self.server_socket:
            self.stop_server()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))  # Use Fusion style for better cross-platform appearance
    window = Server()
    window.show()
    sys.exit(app.exec_())