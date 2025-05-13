import sys
import os
import socket
import threading
import tempfile
import platform
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                             QFrame, QStyleFactory, QCheckBox, QTabWidget,
                             QGroupBox, QScrollArea, QFormLayout)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPalette, QFont
from old.encryption import decrypt_file

# Icon and graphics resources would normally be loaded from files
# For this example, we'll use Python's built-in icons or simple styling
# In a production app, you should use proper resources

class WorkerSignals(QObject):
    """Define signals available for the worker thread."""
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    received = pyqtSignal(str, str)  # File path and original filename
    progress = pyqtSignal(int)  # Progress percentage
    client_connected = pyqtSignal(str)  # Client address
    client_disconnected = pyqtSignal(str)  # Client address

class ConnectionStatus(QWidget):
    """Custom widget to show connection status with animation"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.online = False
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Status indicator
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet("background-color: red; border-radius: 8px;")
        layout.addWidget(self.status_indicator)
        
        # Status text
        self.status_text = QLabel("Offline")
        font = QFont()
        font.setBold(True)
        self.status_text.setFont(font)
        layout.addWidget(self.status_text)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def set_status(self, online):
        """Update status visualization"""
        self.online = online
        
        if online:
            self.status_indicator.setStyleSheet("background-color: #4CAF50; border-radius: 8px;")
            self.status_text.setText("Online")
            self.status_text.setStyleSheet("color: #4CAF50;")
        else:
            self.status_indicator.setStyleSheet("background-color: #F44336; border-radius: 8px;")
            self.status_text.setText("Offline")
            self.status_text.setStyleSheet("color: #F44336;")
            
        # Add a pulse animation
        self.pulse_animation()
    
    def pulse_animation(self):
        """Create a pulse animation for the status indicator"""
        self.animation = QPropertyAnimation(self.status_indicator, b"size")
        self.animation.setDuration(300)
        self.animation.setStartValue(QSize(16, 16))
        self.animation.setEndValue(QSize(20, 20))
        self.animation.setEasingCurve(QEasingCurve.OutQuad)
        self.animation.start()
        
        # Reset size after animation
        def reset_size():
            self.status_indicator.setFixedSize(16, 16)
        
        self.animation.finished.connect(reset_size)

class FileReceiveWidget(QFrame):
    """Widget to display information about received files"""
    def __init__(self, filename, path, size, timestamp):
        super().__init__()
        self.filename = filename
        self.path = path
        self.size = size
        self.timestamp = timestamp
        
        self.init_ui()
        
    def init_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            FileReceiveWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #f9f9f9;
                margin: 5px;
            }
            FileReceiveWidget:hover {
                background-color: #e9e9e9;
                border: 1px solid #ccc;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # File name with icon
        file_header = QHBoxLayout()
        file_icon = QLabel("📄")  # Using emoji as a placeholder for file icon
        file_icon.setStyleSheet("font-size: 20px;")
        file_header.addWidget(file_icon)
        
        file_name = QLabel(self.filename)
        file_name.setStyleSheet("font-weight: bold; font-size: 14px;")
        file_header.addWidget(file_name, 1)
        
        layout.addLayout(file_header)
        
        # File details
        details_layout = QFormLayout()
        details_layout.setContentsMargins(20, 0, 0, 0)
        
        path_label = QLabel(self.path)
        path_label.setToolTip(self.path)
        path_label.setStyleSheet("color: #666;")
        
        # Format size nicely
        size_str = self.format_size(self.size)
        
        details_layout.addRow("Saved to:", path_label)
        details_layout.addRow("Size:", QLabel(size_str))
        details_layout.addRow("Received:", QLabel(self.timestamp))
        
        layout.addLayout(details_layout)
        
        # Actions
        action_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        open_folder_btn.clicked.connect(lambda: self.open_folder(os.path.dirname(self.path)))
        
        open_file_btn = QPushButton("Open File")
        open_file_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        open_file_btn.clicked.connect(lambda: self.open_file(self.path))
        
        action_layout.addWidget(open_folder_btn)
        action_layout.addWidget(open_file_btn)
        
        layout.addLayout(action_layout)
        self.setLayout(layout)
    
    def format_size(self, size_bytes):
        """Format size in bytes to human-readable format"""
        if size_bytes < 1024:
            return f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f} GB"
    
    def open_folder(self, path):
        """Open the containing folder in file explorer"""
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            os.system(f"open '{path}'")
        else:  # Linux
            os.system(f"xdg-open '{path}'")
    
    def open_file(self, path):
        """Open the file with default application"""
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":  # macOS
            os.system(f"open '{path}'")
        else:  # Linux
            os.system(f"xdg-open '{path}'")
            
    def mousePressEvent(self, event):
        """Add a subtle click effect"""
        self.setStyleSheet("""
            FileReceiveWidget {
                border: 1px solid #bbb;
                border-radius: 5px;
                background-color: #e5e5e5;
                margin: 5px;
            }
        """)
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """Reset style on mouse release"""
        self.setStyleSheet("""
            FileReceiveWidget {
                border: 1px solid #ddd;
                border-radius: 5px;
                background-color: #f9f9f9;
                margin: 5px;
            }
            FileReceiveWidget:hover {
                background-color: #e9e9e9;
                border: 1px solid #ccc;
            }
        """)
        super().mouseReleaseEvent(event)

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))  # Modern cross-platform style
    window = Server()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()