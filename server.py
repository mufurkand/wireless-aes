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
                            QFrame, QStyleFactory, QCheckBox, QSplitter, QTabWidget,
                            QGridLayout, QGroupBox, QScrollArea, QFormLayout, QToolButton)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon, QPixmap, QFontDatabase
from encryption import decrypt_file

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

class Server(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Transfer - Server")
        self.setMinimumSize(900, 600)
        
        self.server_socket = None
        self.is_running = False
        self.save_directory = os.path.expanduser("~/Downloads")
        self.dark_mode = False
        self.received_files = []
        self.connected_clients = set()
        
        # Load custom fonts 
        self.load_fonts()
        
        self.init_ui()
    
    def load_fonts(self):
        """Load custom fonts for better visual appearance"""
        # In a real app, you'd load actual font files
        # Here we just ensure consistent font usage
        self.title_font = QFont()
        self.title_font.setPointSize(14)
        self.title_font.setBold(True)
        
        self.subtitle_font = QFont()
        self.subtitle_font.setPointSize(12)
        self.subtitle_font.setBold(True)
        
        self.normal_font = QFont()
        self.normal_font.setPointSize(10)
    
    def init_ui(self):
        # Main widget with tab interface
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.dashboard_tab = QWidget()
        self.files_tab = QWidget()
        self.log_tab = QWidget()
        self.settings_tab = QWidget()
        
        self.setup_dashboard_tab()
        self.setup_files_tab()
        self.setup_log_tab()
        self.setup_settings_tab()
        
        # Add tabs to widget
        self.tab_widget.addTab(self.dashboard_tab, "Dashboard")
        self.tab_widget.addTab(self.files_tab, "Files")
        self.tab_widget.addTab(self.log_tab, "Logs")
        self.tab_widget.addTab(self.settings_tab, "Settings")
        
        self.setCentralWidget(self.tab_widget)
        
        # Status bar with connection status
        self.status_bar = self.statusBar()
        self.connection_status = ConnectionStatus()
        self.status_bar.addPermanentWidget(self.connection_status)
        self.status_bar.showMessage("Server ready")
        
        # Apply initial styles
        self.apply_styles()
    
    def setup_dashboard_tab(self):
        """Set up the main dashboard tab"""
        layout = QVBoxLayout()
        
        # Server status panel
        status_group = QGroupBox("Server Status")
        status_group.setFont(self.subtitle_font)
        status_layout = QVBoxLayout()
        
        # Header with status and controls
        header_layout = QHBoxLayout()
        
        # Status info
        info_layout = QVBoxLayout()
        
        self.dashboard_status_label = QLabel("Server is not running")
        self.dashboard_status_label.setFont(self.title_font)
        self.dashboard_status_label.setStyleSheet("color: #F44336;")
        info_layout.addWidget(self.dashboard_status_label)
        
        self.dashboard_info_label = QLabel("Configure and start the server to receive files")
        info_layout.addWidget(self.dashboard_info_label)
        
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        # Server controls
        control_layout = QVBoxLayout()
        
        self.toggle_server_button = QPushButton("Start Server")
        self.toggle_server_button.setMinimumHeight(50)
        self.toggle_server_button.setMinimumWidth(150)
        self.toggle_server_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.toggle_server_button.clicked.connect(self.toggle_server)
        control_layout.addWidget(self.toggle_server_button)
        
        header_layout.addLayout(control_layout)
        status_layout.addLayout(header_layout)
        
        # Server details
        details_layout = QFormLayout()
        details_layout.setVerticalSpacing(10)
        
        # Port input with validation
        port_layout = QHBoxLayout()
        self.port_input = QLineEdit("5000")
        self.port_input.setPlaceholderText("Port (1024-65535)")
        self.port_input.textChanged.connect(self.validate_port_input)
        self.port_input.setMaximumWidth(150)
        port_layout.addWidget(self.port_input)
        
        # Port status indicator
        self.port_status = QLabel("✓")
        self.port_status.setStyleSheet("color: green;")
        port_layout.addWidget(self.port_status)
        
        details_layout.addRow("Port:", port_layout)
        
        # Password field with show/hide toggle
        password_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter encryption password")
        self.password_input.textChanged.connect(self.validate_password_input)
        
        password_layout.addWidget(self.password_input)
        
        self.show_password = QCheckBox("Show")
        self.show_password.toggled.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.show_password)
        
        # Password status indicator
        self.password_status = QLabel("×")
        self.password_status.setStyleSheet("color: red;")
        password_layout.addWidget(self.password_status)
        
        details_layout.addRow("Password:", password_layout)
        
        # Save directory
        save_dir_layout = QHBoxLayout()
        self.save_dir_display = QLineEdit(self.save_directory)
        self.save_dir_display.setReadOnly(True)
        save_dir_layout.addWidget(self.save_dir_display)
        
        self.save_dir_button = QPushButton("Browse...")
        self.save_dir_button.clicked.connect(self.select_save_directory)
        save_dir_layout.addWidget(self.save_dir_button)
        
        details_layout.addRow("Save Location:", save_dir_layout)
        
        status_layout.addLayout(details_layout)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Current Activity
        activity_group = QGroupBox("Current Activity")
        activity_group.setFont(self.subtitle_font)
        activity_layout = QVBoxLayout()
        
        # Active clients label
        client_header = QHBoxLayout()
        client_header.addWidget(QLabel("Connected Clients:"))
        self.client_count_label = QLabel("0")
        self.client_count_label.setStyleSheet("font-weight: bold;")
        client_header.addWidget(self.client_count_label)
        client_header.addStretch()
        activity_layout.addLayout(client_header)
        
        # Connected clients list
        self.client_list = QTextEdit()
        self.client_list.setReadOnly(True)
        self.client_list.setMaximumHeight(60)
        self.client_list.setPlaceholderText("No clients connected")
        activity_layout.addWidget(self.client_list)
        
        # Current transfer progress
        progress_header = QHBoxLayout()
        progress_header.addWidget(QLabel("Current Transfer:"))
        self.transfer_status_label = QLabel("No active transfers")
        self.transfer_status_label.setStyleSheet("font-style: italic;")
        progress_header.addWidget(self.transfer_status_label)
        progress_header.addStretch()
        activity_layout.addLayout(progress_header)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% - %v / %m")
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 5px;
            }
        """)
        activity_layout.addWidget(self.progress_bar)
        
        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)
        
        # Recent Files
        recent_group = QGroupBox("Recently Received Files")
        recent_group.setFont(self.subtitle_font)
        recent_layout = QVBoxLayout()
        
        self.recent_files_label = QLabel("No files received yet")
        self.recent_files_label.setStyleSheet("font-style: italic;")
        recent_layout.addWidget(self.recent_files_label)
        
        # Recent files scroll area
        recent_scroll = QScrollArea()
        recent_scroll.setWidgetResizable(True)
        recent_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.recent_files_container = QWidget()
        self.recent_files_layout = QVBoxLayout(self.recent_files_container)
        self.recent_files_layout.setAlignment(Qt.AlignTop)
        
        recent_scroll.setWidget(self.recent_files_container)
        recent_layout.addWidget(recent_scroll)
        
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)
        
        self.dashboard_tab.setLayout(layout)
    
    def setup_files_tab(self):
        """Set up the files tab with received files history"""
        layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Received Files")
        header_label.setFont(self.title_font)
        header_layout.addWidget(header_label)
        
        # Search field placeholder (could be implemented in the future)
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search files...")
        search_input.setMaximumWidth(250)
        header_layout.addStretch()
        header_layout.addWidget(search_input)
        
        layout.addLayout(header_layout)
        
        # Files list in a scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.files_container = QWidget()
        self.files_layout = QVBoxLayout(self.files_container)
        self.files_layout.setAlignment(Qt.AlignTop)
        self.files_layout.setSpacing(10)
        
        scroll_area.setWidget(self.files_container)
        layout.addWidget(scroll_area)
        
        # Placeholder text when no files
        self.files_placeholder = QLabel("No files have been received yet")
        self.files_placeholder.setAlignment(Qt.AlignCenter)
        self.files_placeholder.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
        self.files_layout.addWidget(self.files_placeholder)
        
        self.files_tab.setLayout(layout)
    
    def setup_log_tab(self):
        """Set up the log tab with detailed logs"""
        layout = QVBoxLayout()
        
        # Log controls
        controls_layout = QHBoxLayout()
        
        log_level_label = QLabel("Log Level:")
        controls_layout.addWidget(log_level_label)
        
        # Log level selection (placeholder for future functionality)
        log_levels = ["All", "Info", "Warnings", "Errors"]
        for level in log_levels:
            level_btn = QPushButton(level)
            level_btn.setCheckable(True)
            if level == "All":
                level_btn.setChecked(True)
            level_btn.setMaximumWidth(100)
            controls_layout.addWidget(level_btn)
        
        controls_layout.addStretch()
        
        # Clear log button
        self.clear_log_button = QPushButton("Clear Log")
        self.clear_log_button.clicked.connect(self.clear_log)
        controls_layout.addWidget(self.clear_log_button)
        
        layout.addLayout(controls_layout)
        
        # Log display
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QTextEdit.NoWrap)  # Better for log viewing
        self.log_display.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                background-color: #f8f8f8;
            }
        """)
        layout.addWidget(self.log_display)
        
        self.log_tab.setLayout(layout)
    
    def setup_settings_tab(self):
        """Set up the settings tab"""
        layout = QVBoxLayout()
        
        # General settings
        general_group = QGroupBox("General Settings")
        general_group.setFont(self.subtitle_font)
        general_layout = QVBoxLayout()
        
        # Dark mode toggle
        dark_mode_layout = QHBoxLayout()
        dark_mode_layout.addWidget(QLabel("Dark Mode:"))
        self.dark_mode_toggle = QCheckBox()
        self.dark_mode_toggle.toggled.connect(self.toggle_dark_mode)
        dark_mode_layout.addWidget(self.dark_mode_toggle)
        dark_mode_layout.addStretch()
        general_layout.addLayout(dark_mode_layout)
        
        # Auto-start option
        autostart_layout = QHBoxLayout()
        autostart_layout.addWidget(QLabel("Start server automatically:"))
        autostart_toggle = QCheckBox()
        autostart_layout.addWidget(autostart_toggle)
        autostart_layout.addStretch()
        general_layout.addLayout(autostart_layout)
        
        # Default save location
        default_save_layout = QHBoxLayout()
        default_save_layout.addWidget(QLabel("Default Save Location:"))
        self.default_save_input = QLineEdit(self.save_directory)
        default_save_layout.addWidget(self.default_save_input)
        default_save_btn = QPushButton("Browse...")
        default_save_btn.clicked.connect(self.select_default_save_directory)
        default_save_layout.addWidget(default_save_btn)
        general_layout.addLayout(default_save_layout)
        
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)
        
        # Security settings
        security_group = QGroupBox("Security Settings")
        security_group.setFont(self.subtitle_font)
        security_layout = QVBoxLayout()
        
        # Password requirement
        password_req_layout = QHBoxLayout()
        password_req_layout.addWidget(QLabel("Require password for all transfers:"))
        password_req_toggle = QCheckBox()
        password_req_toggle.setChecked(True)
        password_req_toggle.setEnabled(False)  # Always required in this version
        password_req_layout.addWidget(password_req_toggle)
        password_req_layout.addStretch()
        security_layout.addLayout(password_req_layout)
        
        # Connection limit
        conn_limit_layout = QHBoxLayout()
        conn_limit_layout.addWidget(QLabel("Maximum simultaneous connections:"))
        conn_limit_input = QLineEdit("5")
        conn_limit_input.setMaximumWidth(50)
        conn_limit_layout.addWidget(conn_limit_input)
        conn_limit_layout.addStretch()
        security_layout.addLayout(conn_limit_layout)
        
        security_group.setLayout(security_layout)
        layout.addWidget(security_group)
        
        # About section
        about_group = QGroupBox("About")
        about_group.setFont(self.subtitle_font)
        about_layout = QVBoxLayout()
        
        about_text = QLabel("Secure File Transfer - Server Application\nVersion 2.0\n\n"
                           "A secure file transfer solution with end-to-end encryption.")
        about_text.setWordWrap(True)
        about_layout.addWidget(about_text)
        
        about_group.setLayout(about_layout)
        layout.addWidget(about_group)
        
        # Add stretch to push everything up
        layout.addStretch()
        
        self.settings_tab.setLayout(layout)
    
    def select_save_directory(self):
        """Open dialog to select save directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_directory,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.save_directory = directory
            self.save_dir_display.setText(directory)
            self.default_save_input.setText(directory)
            self.log_message(f"Save directory set to: {directory}")
    
    def select_default_save_directory(self):
        """Open dialog to select default save directory from settings tab"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Default Save Directory", self.save_directory,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.save_directory = directory
            self.save_dir_display.setText(directory)
            self.default_save_input.setText(directory)
            self.log_message(f"Default save directory set to: {directory}")
    
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
            
            # Update UI
            self.toggle_server_button.setText("Stop Server")
            self.toggle_server_button.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                    padding: 10px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
            """)
            
            self.dashboard_status_label.setText("Server is running")
            self.dashboard_status_label.setStyleSheet("color: #4CAF50;")
            self.dashboard_info_label.setText(f"Listening on port {port}, files will be saved to {self.save_directory}")
            
            self.status_bar.showMessage(f"Server running on port {port}")
            self.connection_status.set_status(True)
            
            # Disable inputs while server is running
            self.toggle_ui_elements(False)
            
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
            self.log_message(f"Error: {str(e)}", error=True)
    
    def stop_server(self):
        """Stop the server"""
        if self.server_socket:
            self.is_running = False
            self.server_socket.close()
            self.server_socket = None
            
            # Update UI
            self.toggle_server_button.setText("Start Server")
            self.toggle_server_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                    padding: 10px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        
        self.dashboard_status_label.setText("Server is not running")
        self.dashboard_status_label.setStyleSheet("color: #F44336;")
        self.dashboard_info_label.setText("Configure and start the server to receive files")
        
        self.status_bar.showMessage("Server stopped")
        self.connection_status.set_status(False)
        
        # Enable inputs
        self.toggle_ui_elements(True)
        
        # Clear client list
        self.connected_clients.clear()
        self.update_client_list()
        
        self.log_message("Server stopped")
                                                    
    def validate_inputs(self):
        """Validate port and password before starting server"""
        # Validate port
        try:
            port = int(self.port_input.text())
            if port < 1024 or port > 65535:
                QMessageBox.warning(self, "Invalid Port", "Port must be between 1024 and 65535")
                return False
        except ValueError:
            QMessageBox.warning(self, "Invalid Port", "Port must be a number")
            return False
        
        # Validate password
        if not self.password_input.text():
            QMessageBox.warning(self, "Missing Password", "Please enter an encryption password")
            return False
        
        return True
    
    def validate_port_input(self):
        """Validate port input as user types"""
        try:
            port = int(self.port_input.text())
            if port >= 1024 and port <= 65535:
                self.port_status.setText("✓")
                self.port_status.setStyleSheet("color: green;")
            else:
                self.port_status.setText("×")
                self.port_status.setStyleSheet("color: red;")
        except ValueError:
            if self.port_input.text():  # Only show error if there's text
                self.port_status.setText("×")
                self.port_status.setStyleSheet("color: red;")
            else:
                self.port_status.setText("")
    
    def validate_password_input(self):
        """Validate password input as user types"""
        password = self.password_input.text()
        if password:
            self.password_status.setText("✓")
            self.password_status.setStyleSheet("color: green;")
        else:
            self.password_status.setText("×")
            self.password_status.setStyleSheet("color: red;")
    
    def toggle_password_visibility(self, checked):
        """Toggle password visibility"""
        if checked:
            self.password_input.setEchoMode(QLineEdit.Normal)
        else:
            self.password_input.setEchoMode(QLineEdit.Password)
    
    def toggle_ui_elements(self, enabled):
        """Enable or disable UI elements while server is running"""
        self.port_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.save_dir_button.setEnabled(enabled)
        self.show_password.setEnabled(enabled)
    
    def toggle_dark_mode(self, enabled):
        """Toggle dark mode"""
        self.dark_mode = enabled
        
        if enabled:
            # Dark mode palette
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, QColor(0, 0, 0))
            palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
            palette.setColor(QPalette.Text, QColor(255, 255, 255))
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
            self.setPalette(palette)
            
            # Dark mode styles for text fields
            self.setStyleSheet("""
                QTextEdit, QLineEdit {
                    background-color: #2d2d2d;
                    color: #ffffff;
                    border: 1px solid #555555;
                }
                QGroupBox {
                    border: 1px solid #555555;
                }
                FileReceiveWidget {
                    border: 1px solid #555555;
                    background-color: #3d3d3d;
                }
                FileReceiveWidget:hover {
                    background-color: #454545;
                    border: 1px solid #666666;
                }
            """)
        else:
            # Reset to default light theme
            self.setPalette(QApplication.style().standardPalette())
            self.setStyleSheet("")
        
        # Re-apply specific styles for certain widgets
        self.apply_styles()
    
    def apply_styles(self):
        """Apply styles to widgets that need special styling"""
        # Progress bar styling (preserves color in both modes)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 5px;
            }
        """)
    
    def accept_connections(self, password):
        """Accept incoming connections and handle them in separate threads"""
        worker_signals = WorkerSignals()
        worker_signals.status.connect(self.update_status)
        worker_signals.error.connect(self.handle_error)
        worker_signals.received.connect(self.handle_received_file)
        worker_signals.progress.connect(self.update_progress)
        worker_signals.client_connected.connect(self.handle_client_connected)
        worker_signals.client_disconnected.connect(self.handle_client_disconnected)
        
        while self.is_running:
            try:
                client_socket, address = self.server_socket.accept()
                
                # Update the UI with new connection
                worker_signals.client_connected.emit(f"{address[0]}:{address[1]}")
                
                # Start a new thread to handle this client
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address, password, worker_signals),
                    daemon=True
                )
                client_thread.start()
                
            except OSError:
                # Socket was closed, probably when stopping the server
                break
            except Exception as e:
                worker_signals.error.emit(f"Error accepting connection: {str(e)}")
    
    def handle_client(self, client_socket, address, password, signals):
        """Handle client connection and file transfer"""
        client_address = f"{address[0]}:{address[1]}"
        try:
            # Receive file info (size and name)
            info_data = client_socket.recv(1024).decode('utf-8')
            if not info_data:
                signals.error.emit(f"No data received from {client_address}")
                return
            
            file_name, file_size = info_data.split('<SEPARATOR>', 1)
            file_size = int(file_size)
            
            signals.status.emit(f"Receiving file: {file_name} ({file_size} bytes) from {client_address}")
            
            # Create temporary file to store encrypted data
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Receive and write encrypted data
                received_bytes = 0
                while received_bytes < file_size:
                    bytes_left = file_size - received_bytes
                    chunk_size = min(4096, bytes_left)  # Read in chunks of 4KB
                    
                    chunk = client_socket.recv(chunk_size)
                    if not chunk:
                        break
                    
                    temp_file.write(chunk)
                    received_bytes += len(chunk)
                    
                    # Update progress
                    progress_percent = int((received_bytes / file_size) * 100)
                    signals.progress.emit(progress_percent)
            
            # Decrypt the file and save to final destination
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_path = os.path.join(self.save_directory, file_name)
            
            # Make sure we don't overwrite existing files
            if os.path.exists(save_path):
                base_name, extension = os.path.splitext(file_name)
                counter = 1
                while os.path.exists(save_path):
                    save_path = os.path.join(self.save_directory, 
                                            f"{base_name}_{counter}{extension}")
                    counter += 1
            
            # Decrypt the file
            try:
                decrypt_file(temp_path, save_path, password)
                os.unlink(temp_path)  # Delete the temporary encrypted file
                
                signals.status.emit(f"File received and decrypted: {save_path}")
                signals.received.emit(save_path, file_name)
                
            except Exception as e:
                signals.error.emit(f"Decryption error: {str(e)}")
                os.unlink(temp_path)  # Clean up the temp file
                return
            
            # Send confirmation to client
            client_socket.send(b"OK")
            
        except Exception as e:
            signals.error.emit(f"Error handling client {client_address}: {str(e)}")
        finally:
            # Clean up
            client_socket.close()
            signals.client_disconnected.emit(client_address)
    
    def handle_client_connected(self, address):
        """Handle new client connection in the UI"""
        self.connected_clients.add(address)
        self.update_client_list()
        self.log_message(f"Client connected: {address}")
    
    def handle_client_disconnected(self, address):
        """Handle client disconnection in the UI"""
        if address in self.connected_clients:
            self.connected_clients.remove(address)
        self.update_client_list()
        self.log_message(f"Client disconnected: {address}")
    
    def update_client_list(self):
        """Update the client list display"""
        self.client_count_label.setText(str(len(self.connected_clients)))
        
        if self.connected_clients:
            self.client_list.clear()
            for client in self.connected_clients:
                self.client_list.append(client)
        else:
            self.client_list.clear()
            self.client_list.setPlaceholderText("No clients connected")
    
    def update_status(self, message):
        """Update the status display"""
        self.status_bar.showMessage(message)
        self.transfer_status_label.setText(message)
        self.log_message(message)
    
    def handle_error(self, error_message):
        """Handle error messages"""
        self.log_message(error_message, error=True)
        self.status_bar.showMessage(f"Error: {error_message}")
        # In a real app, you might want to show a notification for errors
    
    def update_progress(self, percent):
        """Update the progress bar"""
        self.progress_bar.setValue(percent)
    
    def handle_received_file(self, file_path, original_name):
        """Handle a successfully received file"""
        # Get file information
        file_size = os.path.getsize(file_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create a file widget and add to both recent files and files history
        file_widget = FileReceiveWidget(original_name, file_path, file_size, timestamp)
        
        # Add to dashboard recent files
        if self.recent_files_label.isVisible():
            self.recent_files_label.hide()
        
        # Keep only last 5 recent files
        while self.recent_files_layout.count() >= 5:
            item = self.recent_files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.recent_files_layout.addWidget(file_widget)
        
        # Add to files tab
        if self.files_placeholder.isVisible():
            self.files_placeholder.hide()
        
        # Add a copy of the widget to the files tab
        file_widget_copy = FileReceiveWidget(original_name, file_path, file_size, timestamp)
        self.files_layout.insertWidget(0, file_widget_copy)  # Add at the top
        
        # Add to received files list
        self.received_files.append({
            'name': original_name,
            'path': file_path,
            'size': file_size,
            'timestamp': timestamp
        })
        
        # Reset progress bar and status after a short delay
        QThread.msleep(1000)  # Sleep for 1 second
        self.progress_bar.setValue(0)
        self.transfer_status_label.setText("No active transfers")
    
    def log_message(self, message, error=False):
        """Add message to log with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_type = "ERROR" if error else "INFO"
        log_style = "color: red;" if error else ""
        
        log_entry = f"[{timestamp}] [{log_type}] {message}"
        self.log_display.append(f"<span style='{log_style}'>{log_entry}</span>")
    
    def clear_log(self):
        """Clear the log display"""
        self.log_display.clear()
        self.log_message("Log cleared")
    
    def closeEvent(self, event):
        """Clean up when application is closed"""
        if self.is_running:
            self.stop_server()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))  # Modern cross-platform style
    window = Server()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()