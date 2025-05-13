import os

from PyQt5 import Qt
from PyQt5.QtWidgets import QFileDialog, QVBoxLayout, QFrame, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

# New custom file drop area widget
class FileDropArea(QFrame):
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setMinimumHeight(80)

        # Setup layout
        layout = QVBoxLayout(self)
        self.label = QLabel("Drop file here or click to select")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        # Make it clickable too
        self.setCursor(Qt.PointingHandCursor)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("background-color: #e5f3ff;")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                # Only accept the first file if multiple are dropped
                if os.path.isfile(file_path):
                    self.fileDropped.emit(file_path)
                    break

        self.setStyleSheet("")

    def mousePressEvent(self, event):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select File to Send", os.path.expanduser("~")
        )

        if file_path:
            self.fileDropped.emit(file_path)

