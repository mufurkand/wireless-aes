import sys
import os
import socket
import tempfile
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QFileDialog, QTextEdit, QMessageBox, QProgressBar,
                             QFrame, QStyleFactory, QCheckBox, QTabWidget,
                             QGroupBox, QFormLayout, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QColor, QPalette
from encryption import encrypt_file
from datetime import datetime

class DropZone(QFrame):
    fileDropped = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self.setMinimumHeight(100)
        layout = QVBoxLayout()
        self.label = QLabel("Dosya seçmek için sürükle-bırak veya tıkla")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        self.setLayout(layout)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e6f7ff;")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event):
        self.setStyleSheet("")
        urls = event.mimeData().urls()
        if urls and len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if os.path.isfile(file_path):
                self.fileDropped.emit(file_path)
            else:
                QMessageBox.warning(self, "Geçersiz Dosya", "Lütfen geçerli bir dosya seçin")

    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Gönderilecek Dosyayı Seç", os.path.expanduser("~")
        )
        if file_path:
            self.fileDropped.emit(file_path)


class FileTransferWorker(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_transfer = pyqtSignal()

    def __init__(self, host, port, password, file_path):
        super().__init__()
        self.host = host
        self.port = int(port)
        self.password = password
        self.file_path = file_path

    def run(self):
        try:
            temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
            temp_encrypted_path = temp_encrypted.name
            temp_encrypted.close()

            self.status.emit("Dosya şifreleniyor...")
            encrypt_file(self.file_path, temp_encrypted_path, self.password)
            self.status.emit("Dosya şifrelendi")

            filesize = os.path.getsize(temp_encrypted_path)
            filename = os.path.basename(self.file_path)

            self.status.emit(f"{self.host}:{self.port} adresine bağlanılıyor...")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.host, self.port))
            s.settimeout(None)

            file_info = f"{filename}<SEPARATOR>{filesize}"
            s.send(file_info.encode())

            bytes_sent = 0
            with open(temp_encrypted_path, 'rb') as f:
                while bytes_sent < filesize:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    s.sendall(chunk)
                    bytes_sent += len(chunk)
                    progress_percentage = int(bytes_sent / filesize * 100)
                    self.progress.emit(progress_percentage)

            response = s.recv(1024)
            if response == b"OK":
                self.status.emit("Dosya başarıyla gönderildi")
            else:
                self.error.emit(f"Beklenmeyen sunucu yanıtı: {response.decode()}")

            s.close()
            os.unlink(temp_encrypted_path)
            self.finished_transfer.emit()

        except socket.timeout:
            self.error.emit("Bağlantı zaman aşımına uğradı. Sunucu çalışıyor mu?")
        except ConnectionRefusedError:
            self.error.emit("Bağlantı reddedildi. Sunucu çalışıyor mu?")
        except Exception as e:
            self.error.emit(str(e))
            if 'temp_encrypted_path' in locals():
                try:
                    os.unlink(temp_encrypted_path)
                except:
                    pass


class Client(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Güvenli Dosya Transferi - İstemci")
        self.setMinimumSize(900, 600)
        self.selected_file = None
        self.dark_mode = False
        self.init_ui()

    def init_ui(self):
        self.tab_widget = QTabWidget()
        self.dashboard_tab = QWidget()
        self.log_tab = QWidget()
        self.settings_tab = QWidget()

        self.setup_dashboard_tab()
        self.setup_log_tab()
        self.setup_settings_tab()

        self.tab_widget.addTab(self.dashboard_tab, "Ana Sayfa")
        self.tab_widget.addTab(self.log_tab, "Günlük")
        self.tab_widget.addTab(self.settings_tab, "Ayarlar")

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(self.tab_widget)

        self.statusBar().showMessage("Hazır")
        self.connection_status = ConnectionStatus()
        self.statusBar().addPermanentWidget(self.connection_status)

        self.setCentralWidget(main_widget)
        self.apply_styles()

    def setup_dashboard_tab(self):
        layout = QVBoxLayout()

        server_frame = QGroupBox("Sunucu Ayarları")
        server_layout = QFormLayout()

        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("örn. 192.168.1.100")
        server_layout.addRow("Sunucu IP:", self.host_input)

        self.port_input = QLineEdit("5000")
        self.port_input.setPlaceholderText("örn. 5000")
        server_layout.addRow("Port:", self.port_input)

        password_layout = QHBoxLayout()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.show_password = QCheckBox("Şifreyi Göster")
        self.show_password.toggled.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.password_input)
        password_layout.addWidget(self.show_password)
        server_layout.addRow("Şifre:", password_layout)

        server_frame.setLayout(server_layout)
        layout.addWidget(server_frame)

        file_frame = QGroupBox("Dosya Seçimi")
        file_layout = QVBoxLayout()

        self.drop_zone = DropZone()
        self.drop_zone.fileDropped.connect(self.handle_file_dropped)
        file_layout.addWidget(self.drop_zone)

        self.file_path_label = QLabel("Dosya seçilmedi")
        file_layout.addWidget(self.file_path_label)

        self.file_button = QPushButton("Dosya Seç")
        self.file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_button)

        file_frame.setLayout(file_layout)
        layout.addWidget(file_frame)

        transfer_layout = QHBoxLayout()
        self.send_button = QPushButton("Dosya Gönder")
        self.send_button.setMinimumHeight(40)
        self.send_button.setEnabled(False)
        self.send_button.clicked.connect(self.send_file)
        transfer_layout.addWidget(self.send_button)

        self.dark_mode_toggle = QCheckBox("Koyu Mod")
        self.dark_mode_toggle.toggled.connect(self.toggle_dark_mode)
        transfer_layout.addWidget(self.dark_mode_toggle)

        layout.addLayout(transfer_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.transfer_status = QLabel("Hazır")
        layout.addWidget(self.transfer_status)

        self.dashboard_tab.setLayout(layout)

    def setup_log_tab(self):
        layout = QVBoxLayout()
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.log_display)

        clear_btn = QPushButton("Günlüğü Temizle")
        clear_btn.clicked.connect(self.clear_log)
        layout.addWidget(clear_btn)

        self.log_tab.setLayout(layout)

    def setup_settings_tab(self):
        layout = QVBoxLayout()
        dark_mode_group = QGroupBox("Görünüm Ayarları")
        dark_mode_layout = QHBoxLayout()
        self.dark_mode_toggle = QCheckBox("Koyu Mod")
        self.dark_mode_toggle.toggled.connect(self.toggle_dark_mode)
        dark_mode_layout.addWidget(self.dark_mode_toggle)
        dark_mode_group.setLayout(dark_mode_layout)
        layout.addWidget(dark_mode_group)
        layout.addStretch()
        self.settings_tab.setLayout(layout)

    def handle_file_dropped(self, file_path):
        self.selected_file = file_path
        self.file_path_label.setText(os.path.basename(file_path))
        self.send_button.setEnabled(True)
        self.log_message(f"Seçilen dosya: {file_path}")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Gönderilecek Dosyayı Seç", os.path.expanduser("~")
        )
        if file_path:
            self.selected_file = file_path
            self.file_path_label.setText(os.path.basename(file_path))
            self.send_button.setEnabled(True)
            self.log_message(f"Seçilen dosya: {file_path}")

    def send_file(self):
        if not self.validate_inputs():
            return

        host = self.host_input.text()
        port = int(self.port_input.text())
        password = self.password_input.text()

        self.toggle_ui_elements(False)
        self.transfer_status.setText("Dosya gönderiliyor...")
        self.transfer_status.setStyleSheet("color: #0056b3; font-weight: bold;")

        self.worker = FileTransferWorker(host, port, password, self.selected_file)
        self.worker.progress.connect(self.update_progress)
        self.worker.status.connect(lambda msg: self.transfer_status.setText(msg))
        self.worker.status.connect(self.log_message)
        self.worker.error.connect(self.handle_error)
        self.worker.finished_transfer.connect(self.handle_transfer_finished)
        self.worker.start()

    def validate_inputs(self):
        host = self.host_input.text()
        if not host:
            QMessageBox.warning(self, "Geçersiz Sunucu", "Sunucu IP adresi boş olamaz")
            return False

        try:
            port = int(self.port_input.text())
            if port < 1024 or port > 65535:
                raise ValueError("Port 1024 ile 65535 arasında olmalıdır")
        except ValueError as e:
            QMessageBox.warning(self, "Geçersiz Port", str(e))
            return False

        password = self.password_input.text()
        if not password:
            QMessageBox.warning(self, "Geçersiz Şifre", "Şifre alanı boş olamaz")
            return False

        if not self.selected_file:
            QMessageBox.warning(self, "Dosya Seçilmedi", "Lütfen göndermek için bir dosya seçin")
            return False

        return True

    def toggle_ui_elements(self, enabled):
        self.host_input.setEnabled(enabled)
        self.port_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.file_button.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.drop_zone.setEnabled(enabled)
        self.show_password.setEnabled(enabled)
        self.dark_mode_toggle.setEnabled(enabled)

    def update_progress(self, value):
        self.progress_bar.setValue(value)
        if value < 30:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #ff9800; }")
        elif value < 70:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2196f3; }")
        else:
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4caf50; }")

    def handle_error(self, error_msg):
        self.log_message(f"HATA: {error_msg}")
        QMessageBox.critical(self, "Transfer Hatası", error_msg)
        self.toggle_ui_elements(True)
        self.transfer_status.setText("Hata oluştu")
        self.transfer_status.setStyleSheet("color: red; font-weight: bold;")

    def handle_transfer_finished(self):
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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")

    def clear_log(self):
        self.log_display.clear()
        self.log_message("Günlük temizlendi")

    def toggle_password_visibility(self, checked):
        self.password_input.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def toggle_dark_mode(self, checked):
        self.dark_mode = checked
        self.apply_styles()

    def apply_styles(self):
        if self.dark_mode:
            palette = QPalette()
            bg_color = QColor(45, 45, 45)
            text_color = QColor(255, 255, 255)
            palette.setColor(QPalette.Window, bg_color)
            palette.setColor(QPalette.WindowText, text_color)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, bg_color)
            palette.setColor(QPalette.ToolTipBase, bg_color)
            palette.setColor(QPalette.ToolTipText, text_color)
            palette.setColor(QPalette.Text, text_color)
            palette.setColor(QPalette.Button, bg_color)
            palette.setColor(QPalette.ButtonText, text_color)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            self.setPalette(palette)

            self.setStyleSheet("""
                QFrame { border: 1px solid #555; }
                QGroupBox { border: 1px solid #555; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
                QGroupBox::title {
    text-align: center;
    padding: 0 3px;
}
                QProgressBar { border: 1px solid #555; border-radius: 3px; text-align: center; }
                QProgressBar::chunk { border-radius: 3px; }
                QPushButton {
                    background-color: #2a82da;
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #3a92ea; }
                QPushButton:disabled { background-color: #555; color: #888; }
                QLineEdit, QTextEdit {
                    background-color: #333;
                    color: white;
                    border: 1px solid #555;
                    padding: 5px;
                    border-radius: 3px;
                }
                DropZone {
                    background-color: #333;
                    border: 2px dashed #555;
                    border-radius: 5px;
                }
                DropZone:hover { border-color: #2a82da; }
            """)
        else:
            self.setPalette(self.style().standardPalette())
            self.setStyleSheet("""
                QFrame { border: 1px solid #ccc; }
                QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
                QGroupBox::title {
    text-align: center;
    padding: 0 3px;
}
                QProgressBar { border: 1px solid #ccc; border-radius: 3px; text-align: center; }
                QProgressBar::chunk { border-radius: 3px; }
                QPushButton {
                    background-color: #0d6efd;
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                }
                QPushButton:hover { background-color: #0b5ed7; }
                QPushButton:disabled { background-color: #cccccc; color: #666666; }
                QLineEdit, QTextEdit {
                    border: 1px solid #ccc;
                    padding: 5px;
                    border-radius: 3px;
                }
                DropZone {
                    background-color: #f8f9fa;
                    border: 2px dashed #ccc;
                    border-radius: 5px;
                }
                DropZone:hover { border-color: #0d6efd; }
            """)

class ConnectionStatus(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.online = False
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet("background-color: red; border-radius: 8px;")
        layout.addWidget(self.status_indicator)
        self.status_text = QLabel("Offline")
        font = self.status_text.font()
        font.setBold(True)
        self.status_text.setFont(font)
        layout.addWidget(self.status_text)
        layout.addStretch()
        self.setLayout(layout)

    def set_status(self, online):
        self.online = online
        if online:
            self.status_indicator.setStyleSheet("background-color: #4CAF50; border-radius: 8px;")
            self.status_text.setText("Online")
            self.status_text.setStyleSheet("color: #4CAF50;")
        else:
            self.status_indicator.setStyleSheet("background-color: #F44336; border-radius: 8px;")
            self.status_text.setText("Offline")
            self.status_text.setStyleSheet("color: #F44336;")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    window = Client()
    window.show()
    sys.exit(app.exec_())