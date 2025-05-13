import os
from PyQt5.QtWidgets import QFileDialog, QVBoxLayout, QFrame, QLabel
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDragEnterEvent, QDropEvent


class FileDropArea(QFrame):
    # Change signal to emit a list of file paths
    filesDropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Sunken)
        self.setMinimumHeight(80)

        # Setup layout
        layout = QVBoxLayout(self)
        self.label = QLabel("Drop files or folders here or click to select")
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
            file_paths = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                # Accept both files and folders
                if os.path.exists(file_path):
                    file_paths.append(file_path)

            if file_paths:
                self.filesDropped.emit(file_paths)
        self.setStyleSheet("")

    def mousePressEvent(self, event):
        # Allow selecting multiple files
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files to Send", os.path.expanduser("~")
        )

        if file_paths:
            self.filesDropped.emit(file_paths)

    def selectFolder(self):
        """Method to select a folder"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder to Send", os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder_path:
            self.filesDropped.emit([folder_path])