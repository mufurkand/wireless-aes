import sys
import os
import socket
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QLabel, QLineEdit, QPushButton,
                            QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                            QFrame, QStyleFactory, QCheckBox, QSplitter)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QMimeData, QSize
from PyQt5.QtGui import QDragEnterEvent, QDropEvent, QIcon, QColor, QPalette
from encryption import encrypt_file

class DropZone(QFrame):
    """Custom drop zone widget for drag and drop file selection."""
    fileDropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setMinimumHeight(100)
        
        # Set up the layout
        layout = QVBoxLayout()
        self.label = QLabel("Dosya seçmek için sürükle-bırak veya tıkla")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        self.setLayout(layout)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e6f7ff;")  # Light highlight
    
    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self.setStyleSheet("")  # Reset style
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        self.setStyleSheet("")  # Reset style
        urls = event.mimeData().urls()
        if urls and len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                self.fileDropped.emit(file_path)
            else:
                QMessageBox.warning(self, "Geçersiz Dosya", "Lütfen geçerli bir dosya seçin")
    
    def mousePressEvent(self, event):
        """Handle mouse press for file dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Gönderilecek Dosyayı Seç", os.path.expanduser("~")
        )
        
        if file_path:
            self.fileDropped.emit(file_path)

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
            self.status.emit("Dosya şifreleniyor...")
            encrypt_file(self.file_path, temp_encrypted_path, self.password)
            self.status.emit("Dosya şifrelendi")
            
            # Get encrypted file size
            filesize = os.path.getsize(temp_encrypted_path)
            filename = os.path.basename(self.file_path)
            
            # Create socket and connect to server
            self.status.emit(f"{self.host}:{self.port} adresine bağlanılıyor...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Set timeout for connection
            s.settimeout(10)
            s.connect((self.host, self.port))
            s.settimeout(None)  # Reset timeout for data transfer
            self.status.emit("Sunucuya bağlandı")
            
            # Send file info
            file_info = f"{filename}<SEPARATOR>{filesize}"
            s.send(file_info.encode())
            
            # Send encrypted file
            self.status.emit("Şifrelenmiş dosya gönderiliyor...")
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
                self.status.emit("Dosya başarıyla gönderildi")
            else:
                self.error.emit(f"Beklenmeyen sunucu yanıtı: {response.decode()}")
            
            # Clean up
            s.close()
            os.unlink(temp_encrypted_path)
            
            self.finished_transfer.emit()
            
        except socket.timeout:
            self.error.emit("Bağlantı zaman aşımına uğradı. Sunucu çalışıyor mu?")
        except ConnectionRefusedError:
            self.error.emit("Bağlantı reddedildi. Sunucu çalışıyor mu?")
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
        self.setWindowTitle("Güvenli Dosya Transferi - İstemci")
        self.setMinimumSize(700, 500)
        
        self.selected_file = None
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
        
        conn_label = QLabel("Bağlantı Ayarları")
        conn_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        server_layout.addWidget(conn_label)
        
        # Server input fields in a grid
        server_fields = QHBoxLayout()
        
        # Host input
        host_layout = QVBoxLayout()
        host_label = QLabel("Sunucu IP:")
        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("örn. 192.168.1.100")
        host_layout.addWidget(host_label)
        host_layout.addWidget(self.host_input)
        server_fields.addLayout(host_layout, 2)
        
        # Port input
        port_layout = QVBoxLayout()
        port_label = QLabel("Port:")
        self.port_input = QLineEdit("5000")
        self.port_input.setPlaceholderText("örn. 5000")
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.port_input)
        server_fields.addLayout(port_layout, 1)
        
        # Password input
        password_layout = QVBoxLayout()
        password_label = QLabel("Şifre:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Şifre girin")
        
        # Show/hide password checkbox
        self.show_password = QCheckBox("Şifreyi göster")
        self.show_password.toggled.connect(self.toggle_password_visibility)
        
        password_layout.addWidget(password_label)
        password_layout.addWidget(self.password_input)
        password_layout.addWidget(self.show_password)
        server_fields.addLayout(password_layout, 2)
        
        server_layout.addLayout(server_fields)
        main_layout.addWidget(server_frame)
        
        # File selection with drag and drop
        file_frame = QFrame()
        file_frame.setFrameShape(QFrame.StyledPanel)
        file_layout = QVBoxLayout(file_frame)
        
        file_header = QLabel("Dosya Seçimi")
        file_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        file_layout.addWidget(file_header)
        
        # Create drop zone
        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self.handle_file_dropped)
        file_layout.addWidget(self.drop_zone)
        
        # File info
        file_info_layout = QHBoxLayout()
        self.file_path_label = QLabel("Dosya seçilmedi")
        self.file_path_label.setWordWrap(True)
        self.file_button = QPushButton("Dosya Seç")
        self.file_button.clicked.connect(self.select_file)
        
        file_info_layout.addWidget(self.file_path_label, 1)
        file_info_layout.addWidget(self.file_button)
        file_layout.addLayout(file_info_layout)
        
        main_layout.addWidget(file_frame)
        
        # Transfer controls
        transfer_layout = QHBoxLayout()
        
        # Send button
        self.send_button = QPushButton("Dosya Gönder")
        self.send_button.setMinimumHeight(40)
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_file)
        transfer_layout.addWidget(self.send_button)
        
        # Dark mode toggle
        self.dark_mode_toggle = QCheckBox("Koyu Mod")
        self.dark_mode_toggle.toggled.connect(self.toggle_dark_mode)
        transfer_layout.addWidget(self.dark_mode_toggle)
        
        main_layout.addLayout(transfer_layout)
        
        # Progress bar with styled appearance
        progress_frame = QFrame()
        progress_frame.setFrameShape(QFrame.StyledPanel)
        progress_layout = QVBoxLayout(progress_frame)
        
        progress_header = QLabel("İlerleme")
        progress_header.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(progress_header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v / %m")
        self.progress_bar.setMinimumHeight(25)
        progress_layout.addWidget(self.progress_bar)
        
        self.transfer_status = QLabel("Hazır")
        progress_layout.addWidget(self.transfer_status)
        
        main_layout.addWidget(progress_frame)
        
        # Status log
        log_frame = QFrame()
        log_frame.setFrameShape(QFrame.StyledPanel)
        log_layout = QVBoxLayout(log_frame)
        
        log_header = QLabel("İşlem Günlüğü")
        log_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        log_layout.addWidget(log_header)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        main_layout.addWidget(log_frame)
        
        # Set main layout
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Status bar
        self.statusBar().showMessage("Hazır")
        
        # Apply initial styles
        self.apply_styles()
    
    def handle_file_dropped(self, file_path):
        """Handle file dropped on drop zone"""
        self.selected_file = file_path
        self.file_path_label.setText(os.path.basename(file_path))
        self.send_button.setEnabled(True)
        self.log_message(f"Seçilen dosya: {file_path}")
    
    def select_file(self):
        """Open file dialog to select a file to send"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Gönderilecek Dosyayı Seç", os.path.expanduser("~")
        )
        
        if file_path:
            self.selected_file = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.send_button.setEnabled(True)
            self.log_message(f"Seçilen dosya: {file_path}")
    
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
        
        # Update status
        self.transfer_status.setText("Dosya gönderiliyor...")
        self.transfer_status.setStyleSheet("color: #0056b3; font-weight: bold;")
        
        # Create and start worker thread
        self.worker = FileTransferWorker(host, port, password, self.selected_file)
        self.worker.progress.connect(self.update_progress)
        self.worker.status.connect(self.log_message)
        self.worker.status.connect(lambda msg: self.transfer_status.setText(msg))
        self.worker.error.connect(self.handle_error)
        self.worker.finished_transfer.connect(self.handle_transfer_finished)
        
        self.worker.start()
    
    def validate_inputs(self):
        """Validate host, port, password and file selection"""
        # Validate host
        host = self.host_input.text()
        if not host:
            QMessageBox.warning(self, "Geçersiz Sunucu", "Sunucu IP adresi boş olamaz")
            return False
        
        # Validate port
        try:
            port = int(self.port_input.text())
            if port < 1024 or port > 65535:
                raise ValueError("Port 1024 ile 65535 arasında olmalıdır")
        except ValueError as e:
            QMessageBox.warning(self, "Geçersiz Port", str(e))
            return False
        
        # Validate password
        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Geçersiz Şifre", "Şifre alanı boş olamaz")
            return False
        
        # Validate file selection
        if not self.selected_file:
            QMessageBox.warning(self, "Dosya Seçilmedi", "Lütfen göndermek için bir dosya seçin")
            return False
        
        return True
    
    def toggle_ui_elements(self, enabled):
        """Enable or disable UI elements"""
        self.host_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.file_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.drop_zone.setEnabled(enabled)
        self.show_password.setEnabled(enabled)
        self.dark_mode_toggle.setEnabled(enabled)
    
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
    
    def handle_error(self, error_msg):
        """Handle error from worker thread"""
        self.log_message(f"HATA: {error_msg}")
        QMessageBox.critical(self, "Transfer Hatası", error_msg)
        self.toggle_ui_elements(True)
        self.transfer_status.setText("Hata oluştu")
        self.transfer_status.setStyleSheet("color: red; font-weight: bold;")
    
    def handle_transfer_finished(self):
        """Handle completed file transfer"""
        QMessageBox.information(
            self, 
            "Transfer Tamamlandı", 
            f"'{os.path.basename(self.selected_file)}' dosyası başarıyla gönderildi"
        )
        self.progress_bar.setValue(0)
        self.toggle_ui_elements(True)
        self.transfer_status.setText("Transfer tamamlandı")
        self.transfer_status.setStyleSheet("color: green; font-weight: bold;")
    
    def log_message(self, message):
        """Add message to log display"""
        self.log_display.append(message)
    
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
                QFrame { border: 1px solid #555; }
                QProgressBar { border: 1px solid #555; border-radius: 3px; }
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
            
            # Style drop zone
            self.drop_zone.setStyleSheet("""
                DropZone {
                    background-color: #333;
                    border: 2px dashed #555;
                    border-radius: 5px;
                }
                DropZone:hover {
                    border-color: #2a82da;
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
            
            # Style drop zone
            self.drop_zone.setStyleSheet("""
                DropZone {
                    background-color: #f8f9fa;
                    border: 2px dashed #ccc;
                    border-radius: 5px;
                }
                DropZone:hover {
                    border-color: #0d6efd;
                }
            """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))  # Use Fusion style for better cross-platform appearance
    window = Client()
    window.show()
    sys.exit(app.exec_())