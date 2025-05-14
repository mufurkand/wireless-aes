import sys
import os

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                             QTabWidget, QCheckBox, QFrame, QListWidget,
                             QListWidgetItem, QToolButton, QMenu, QAction)
from PyQt5.QtCore import Qt, QSize, QThread, QDir

from drop_area import FileDropArea
from file_transfer import FileTransferWorker


import sys
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                             QTabWidget, QCheckBox, QListWidget, QTableWidget,
                             QTableWidgetItem, QTreeView, QFileSystemModel,
                             QFrame)
from PyQt5.QtCore import Qt
from drop_area import FileDropArea
from file_transfer import FileTransferWorker


class SecureTransferApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Secure File Transfer")
        self.setMinimumSize(1000, 700)
        self.selected_files = []
        self.init_ui()

    def init_ui(self):
        # Dark Theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTextEdit, QListWidget, QTreeView, QTableWidget {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #444;
                padding: 5px;
            }
            QPushButton {
                background-color: #3c3c3c;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #1e1e1e;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: white;
                padding: 10px;
            }
            QTabBar::tab:selected {
                background-color: #4d4d4d;
            }
            
                /* Scrollbar */
            QScrollBar:vertical {
                background: #2d2d2d;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
        
            /* Tablo Header (QHeaderView) */
            QHeaderView::section {
                background-color: #2d2d2d;
                color: white;
                padding: 4px;
                border: 1px solid #444;
            }
        
            /* MessageBox / Dialog Background */
            QMessageBox, QFileDialog {
                background-color: #1e1e1e;
                color: white;
            }
            QDialog {
                background-color: #1e1e1e;
                color: white;
            }
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background-color: #555555;
            }
            
            QScrollBar:horizontal {
                background: #2d2d2d;
                height: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #555555;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            
            QProgressBar {
                border: 1px solid #444;
                background: #6a6a6a;
                height: 12px;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #6a6a6a;
                border-radius: 6px;
            }
            
            """)

        main_widget = QWidget()
        main_layout = QVBoxLayout()

        tab_widget = QTabWidget()
        send_tab = QWidget()
        receive_tab = QWidget()
        tab_widget.addTab(send_tab, "Send Files")
        tab_widget.addTab(receive_tab, "Receive Files")

        # === SEND TAB ===
        send_layout = QVBoxLayout()
        server_layout = QHBoxLayout()
        host_label = QLabel("Server IP:")
        self.host_input = QLineEdit("localhost")
        port_label = QLabel("Port:")
        self.port_input = QLineEdit("5000")
        self.port_input.setFixedWidth(100)
        server_layout.addWidget(host_label)
        server_layout.addWidget(self.host_input)
        server_layout.addWidget(port_label)
        server_layout.addWidget(self.port_input)
        send_layout.addLayout(server_layout)

        self.file_drop_area = FileDropArea()
        self.file_drop_area.filesDropped.connect(self.handle_files_dropped)
        send_layout.addWidget(self.file_drop_area)

        folder_button_layout = QHBoxLayout()
        folder_button_layout.addStretch()
        self.select_folder_button = QPushButton("Select Folder")
        self.select_folder_button.clicked.connect(self.select_folder)
        folder_button_layout.addWidget(self.select_folder_button)
        send_layout.addLayout(folder_button_layout)

        files_label = QLabel("Selected Files:")
        send_layout.addWidget(files_label)
        self.files_list = QListWidget()
        self.files_list.setMinimumHeight(100)
        send_layout.addWidget(self.files_list)

        files_buttons_layout = QHBoxLayout()
        files_buttons_layout.addStretch()
        self.clear_files_button = QPushButton("Clear All")
        self.clear_files_button.clicked.connect(self.clear_file_selection)
        self.clear_files_button.setEnabled(False)
        self.remove_file_button = QPushButton("Remove Selected")
        self.remove_file_button.clicked.connect(self.remove_selected_file)
        self.remove_file_button.setEnabled(False)
        files_buttons_layout.addWidget(self.remove_file_button)
        files_buttons_layout.addWidget(self.clear_files_button)
        send_layout.addLayout(files_buttons_layout)
        self.files_list.itemSelectionChanged.connect(self.update_remove_button_state)

        save_encrypted_layout = QHBoxLayout()
        self.save_encrypted_cb = QCheckBox("Save encrypted version")
        self.save_encrypted_cb.setChecked(True)
        save_encrypted_layout.addWidget(self.save_encrypted_cb)
        save_encrypted_layout.addStretch()
        send_layout.addLayout(save_encrypted_layout)

        self.send_button = QPushButton("Send Files")
        self.send_button.clicked.connect(self.send_files)
        self.send_button.setEnabled(False)
        send_layout.addWidget(self.send_button)

        self.send_progress = QProgressBar()
        self.send_progress.setRange(0, 100)
        self.send_progress.setValue(0)
        send_layout.addWidget(self.send_progress)

        log_label = QLabel("Log:")
        send_layout.addWidget(log_label)
        self.send_log = QTextEdit()
        self.send_log.setReadOnly(True)
        send_layout.addWidget(self.send_log)

        clear_send_layout = QHBoxLayout()
        clear_send_layout.addStretch()
        self.clear_send_log_button = QPushButton("Clear Log")
        self.clear_send_log_button.clicked.connect(self.clear_send_log)
        clear_send_layout.addWidget(self.clear_send_log_button)
        send_layout.addLayout(clear_send_layout)

        send_tab.setLayout(send_layout)

        # === RECEIVE TAB ===
        receive_main_layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        self.save_dir_label = QLabel(os.path.expanduser("~/Downloads"))
        self.select_dir_button = QPushButton("Select Save Directory")
        self.select_dir_button.clicked.connect(self.select_save_directory)
        left_layout.addWidget(self.save_dir_label)

        self.file_system_model = QFileSystemModel()
        self.file_system_model.setRootPath(QDir.rootPath())
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.file_system_model)
        self.tree_view.setRootIndex(self.file_system_model.index(os.path.expanduser("~/Downloads")))
        self.tree_view.setHeaderHidden(True)
        self.tree_view.setSelectionMode(QTreeView.SingleSelection)
        self.tree_view.setSelectionBehavior(QTreeView.SelectRows)
        left_layout.addWidget(self.tree_view)
        left_layout.addWidget(self.select_dir_button)


        middle_layout = QVBoxLayout()
        self.receive_log_label = QLabel("Logs:")
        self.receive_log_label.setStyleSheet("color: white;")


        self.clear_receive_log_button = QPushButton("Clear Log")
        self.clear_receive_log_button.clicked.connect(self.clear_receive_log)

        middle_layout.addWidget(self.receive_log_label)

        self.receive_log = QTextEdit()
        self.receive_log.setReadOnly(True)
        self.receive_log.setStyleSheet("background-color: #2d2d2d; color: white;")
        middle_layout.addWidget(self.receive_log)
        middle_layout.addWidget(self.clear_receive_log_button)

        right_layout = QVBoxLayout()
        transfer_details_label = QLabel("Transfer Details:")
        transfer_details_label.setStyleSheet("color: white;")
        right_layout.addWidget(transfer_details_label)

        self.transfer_details_table = QTableWidget()
        self.transfer_details_table.verticalHeader().setVisible(False)
        self.transfer_details_table.setColumnCount(3)
        self.transfer_details_table.setHorizontalHeaderLabels(["File Name", "Status", "Size"])
        self.transfer_details_table.horizontalHeader().setStretchLastSection(True)
        self.transfer_details_table.setStyleSheet("background-color: #2d2d2d; color: white;")
        right_layout.addWidget(self.transfer_details_table)


        self.clear_table_button = QPushButton("Clear Table")
        self.clear_table_button.clicked.connect(self.clear_transfer_table)
        right_layout.addWidget(self.clear_table_button)

        bottom_layout = QHBoxLayout()
        global_progress_label = QLabel("Overall Progress:")
        global_progress_label.setStyleSheet("color: white;")
        bottom_layout.addWidget(global_progress_label)
        self.global_progress_bar = QProgressBar()
        self.global_progress_bar.setRange(0, 100)
        self.global_progress_bar.setValue(0)
        self.global_progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                background: #1e1e1e;
                height: 12px;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background-color: #00ffaa;
                border-radius: 6px;
            }
        """)
        bottom_layout.addWidget(self.global_progress_bar)

        receive_main_layout.addLayout(left_layout)
        receive_main_layout.addLayout(middle_layout)
        receive_main_layout.addLayout(right_layout)

        receive_layout = QVBoxLayout()
        receive_layout.addLayout(receive_main_layout)
        receive_layout.addLayout(bottom_layout)

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

        receive_encrypted_layout = QHBoxLayout()
        self.receive_encrypted_cb = QCheckBox("Save encrypted version")
        self.receive_encrypted_cb.setChecked(True)
        receive_encrypted_layout.addWidget(self.receive_encrypted_cb)
        receive_encrypted_layout.addStretch()
        receive_layout.addLayout(receive_encrypted_layout)

        self.receive_button = QPushButton("Start Receiving")
        self.receive_button.setCheckable(True)
        self.receive_button.clicked.connect(self.toggle_receiving)
        receive_layout.addWidget(self.receive_button)

        self.receive_progress = QProgressBar()
        self.receive_progress.setRange(0, 100)
        self.receive_progress.setValue(0)
        receive_layout.addWidget(self.receive_progress)

        receive_tab.setLayout(receive_layout)

        main_layout.addWidget(tab_widget)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.statusBar().showMessage("Ready")

    def update_chunk_status(self, filename, chunk_number):
        while self.transfer_details_table.rowCount() > 99:
            self.transfer_details_table.removeRow(0)

        row_position = self.transfer_details_table.rowCount()
        self.transfer_details_table.insertRow(row_position)

        # Chunk Name
        chunk_name_item = QTableWidgetItem(f"{filename} - #{chunk_number}")
        chunk_name_item.setFlags(chunk_name_item.flags() & ~Qt.ItemIsEditable)  # Sadece okunabilir
        self.transfer_details_table.setItem(row_position, 0, chunk_name_item)

        # Status (başlangıçta Receiving...)
        status_item = QTableWidgetItem("⏳ Receiving...")
        status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
        self.transfer_details_table.setItem(row_position, 1, status_item)

        # Size
        size_item = QTableWidgetItem("4 KB")
        size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
        self.transfer_details_table.setItem(row_position, 2, size_item)

        self.transfer_details_table.scrollToBottom()


    def handle_files_dropped(self, file_paths):
        # Add files to the list
        for file_path in file_paths:
            if file_path not in self.selected_files:
                self.selected_files.append(file_path)
                item_name = os.path.basename(file_path)
                # If it's a directory, add a suffix
                if os.path.isdir(file_path):
                    item_name += " [Folder]"
                item = QListWidgetItem(item_name)
                item.setData(Qt.UserRole, file_path)  # Store the full path
                self.files_list.addItem(item)

        self.update_ui_states()
        self.log_message("Send", f"Added {len(file_paths)} file(s)/folder(s)")

    def clear_transfer_table(self):
        self.transfer_details_table.setRowCount(0)

    def select_folder(self):
        self.file_drop_area.selectFolder()

    def update_ui_states(self):
        has_files = len(self.selected_files) > 0
        self.send_button.setEnabled(has_files)
        self.clear_files_button.setEnabled(has_files)
        # Update the drop area text
        if has_files:
            self.file_drop_area.label.setText("Drop more files/folders or click to add more")
        else:
            self.file_drop_area.label.setText("Drop files or folders here or click to select")

    def update_remove_button_state(self):
        self.remove_file_button.setEnabled(len(self.files_list.selectedItems()) > 0)

    def remove_selected_file(self):
        selected_items = self.files_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            file_path = item.data(Qt.UserRole)
            row = self.files_list.row(item)
            self.files_list.takeItem(row)
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)

        self.update_ui_states()
        self.log_message("Send", f"Removed {len(selected_items)} file(s)/folder(s) from selection")

    def clear_file_selection(self):
        self.selected_files = []
        self.files_list.clear()
        self.update_ui_states()
        self.log_message("Send", "File selection cleared")

    def select_save_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir_label.text(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if directory:
            self.save_dir_label.setText(directory)
            self.tree_view.setRootIndex(self.file_system_model.index(directory))
            self.log_message("Receive", f"Save directory set to: {directory}")

    def send_files(self):
        if not self.validate_send_inputs():
            return

        host = self.host_input.text()
        port = int(self.port_input.text())
        save_encrypted = self.save_encrypted_cb.isChecked()

        self.toggle_send_ui(False)

        # Need to modify FileTransferWorker to handle multiple files
        # For now, we'll just send the first file as a placeholder
        if self.selected_files:
            self.worker = FileTransferWorker(host, port, self.selected_files, save_encrypted=save_encrypted)
            self.worker.progress.connect(self.update_send_progress)
            self.worker.status.connect(lambda msg: self.log_message("Send", msg))
            self.worker.error.connect(self.handle_send_error)
            self.worker.finished_transfer.connect(self.handle_send_finished)

            self.worker.start()
        else:
            self.handle_send_error("No files selected for sending")
            self.toggle_send_ui(True)

    def toggle_receiving(self):
        if self.receive_button.isChecked():
            # Start receiving
            if not self.validate_receive_inputs():
                self.receive_button.setChecked(False)
                return
                
            host = self.receive_host_input.text()
            port = int(self.receive_port_input.text())
            save_encrypted = self.receive_encrypted_cb.isChecked()
            
            self.toggle_receive_ui(False)
            self.receive_button.setEnabled(True)
            self.receive_button.setText("Stop Receiving")
            
            # Clean up any existing worker
            self._cleanup_worker()
                
            # Create a new worker
            self.log_message("Receive", f"Starting server on {host}:{port}")
            self.log_message("Receive", "Waiting for incoming connections...")
            
            self.worker = FileTransferWorker(host, port, self.save_dir_label.text(),
                                         is_server=True, save_encrypted=save_encrypted)
            self.worker.progress.connect(self.update_receive_progress)
            self.worker.status.connect(lambda msg: self.log_message("Receive", msg))
            self.worker.error.connect(self.handle_receive_error)
            self.worker.finished_transfer.connect(self.handle_receive_continuous)
            self.worker.chunk_received.connect(self.update_chunk_status)
            self.worker.chunk_received.connect(self.mark_chunk_received)
            
            self.worker.start()
        else:
            # Stop receiving
            self._cleanup_worker()
            
            self.receive_button.setText("Start Receiving")
            self.toggle_receive_ui(True)
            self.receive_progress.setValue(0)

    def mark_chunk_received(self, filename, chunk_number):
        # Tablo var mı?
        if not hasattr(self, 'transfer_details_table') or self.transfer_details_table is None:
            return

        target_text = f"{filename} - #{chunk_number}"

        # Satır sayısı kontrolü
        for row in range(self.transfer_details_table.rowCount()):
            # Hücrenin varlığı kontrol ediliyor
            name_item = self.transfer_details_table.item(row, 0)
            if name_item is None:
                continue

            if name_item.text() == target_text:
                status_item = self.transfer_details_table.item(row, 1)
                if status_item:
                    try:
                        status_item.setText("✔️ Received")
                    except Exception as e:
                        print(f"Error updating row: {e}")
                break

    def _cleanup_worker(self):
        """Safely clean up the worker thread"""
        if hasattr(self, 'worker') and self.worker is not None:
            try:
                if self.worker.isRunning():
                    self.log_message("Receive", "Stopping server...")
                    self.worker.terminate()
                    self.worker.wait()
                    self.log_message("Receive", "Server stopped")
            except RuntimeError:
                # Object might already be deleted
                self.log_message("Receive", "Worker already cleaned up")
                
            # Set worker to None to prevent further access
            self.worker = None
            
            # Give the OS a moment to fully release the socket
            QThread.msleep(500)  # Sleep for 500ms

    def start_receiving(self):
        # Legacy method now redirects to toggle_receiving
        self.receive_button.setChecked(True)
        self.toggle_receiving()

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

        if not self.selected_files:
            QMessageBox.warning(self, "No Files Selected", "Please select at least one file or folder to send")
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
        self.send_button.setEnabled(enabled and len(self.selected_files) > 0)
        self.save_encrypted_cb.setEnabled(enabled)
        self.select_folder_button.setEnabled(enabled)
        self.files_list.setEnabled(enabled)
        self.clear_files_button.setEnabled(enabled and len(self.selected_files) > 0)
        self.remove_file_button.setEnabled(enabled and len(self.files_list.selectedItems()) > 0)

    def toggle_receive_ui(self, enabled):
        self.receive_host_input.setEnabled(enabled)
        self.receive_port_input.setEnabled(enabled)
        self.select_dir_button.setEnabled(enabled)
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
        
        # Check if we're still in receiving mode before showing error dialog
        if self.receive_button.isChecked():
            QMessageBox.critical(self, "Receive Error", error_msg)
            
            # Reset the button state
            self.receive_button.setChecked(False)
            self.receive_button.setText("Start Receiving")
            
            # Clean up the worker
            self._cleanup_worker()
            
        # Always re-enable the UI
        self.toggle_receive_ui(True)

    def handle_send_finished(self):
        QMessageBox.information(
            self,
            "Send Complete",
            f"{len(self.selected_files)} file(s)/folder(s) have been sent successfully"
        )
        self.send_progress.setValue(0)
        self.toggle_send_ui(True)

    def handle_receive_continuous(self):
        """Handle completed file transfer in continuous mode"""
        self.receive_progress.setValue(0)
        
        # Only show message box if the button is not checked anymore (stopped)
        if not self.receive_button.isChecked():
            QMessageBox.information(
                self,
                "Receive Complete",
                "Files have been received and decrypted successfully"
            )
            self.toggle_receive_ui(True)
        else:
            # Ready for next transfer
            self.log_message("Receive", "Transfer complete. Ready for more files...")

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