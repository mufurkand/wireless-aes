import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                             QTabWidget, QCheckBox, QFrame)

from drop_area import FileDropArea
from file_transfer import FileTransferWorker
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

        # File drop area (replaces the old file selection)
        self.file_drop_area = FileDropArea()
        self.file_drop_area.fileDropped.connect(self.handle_file_dropped)
        send_layout.addWidget(self.file_drop_area)

        # File information display
        self.file_info_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        self.file_info_layout.addWidget(self.file_path_label)

        # Clear file selection button
        self.clear_file_button = QPushButton("Clear")
        self.clear_file_button.clicked.connect(self.clear_file_selection)
        self.clear_file_button.setVisible(False)  # Hide initially
        self.file_info_layout.addWidget(self.clear_file_button)

        send_layout.addLayout(self.file_info_layout)

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

    def handle_file_dropped(self, file_path):
        self.selected_file = file_path
        self.file_path_label.setText(os.path.basename(file_path))
        self.send_button.setEnabled(True)
        self.log_message("Send", f"Selected file: {file_path}")

        # Show the clear button when a file is selected
        self.clear_file_button.setVisible(True)

        # Change the drop area text to show file is selected
        self.file_drop_area.label.setText("File selected - Drop another to change")

    def clear_file_selection(self):
        self.selected_file = None
        self.file_path_label.setText("No file selected")
        self.send_button.setEnabled(False)
        self.clear_file_button.setVisible(False)
        self.file_drop_area.label.setText("Drop file here or click to select")
        self.log_message("Send", "File selection cleared")

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
        self.file_drop_area.setEnabled(enabled)
        self.clear_file_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled and self.selected_file is not None)
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