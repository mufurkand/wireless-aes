import sys
from PyQt5.QtWidgets import (QApplication)
from secure_transfer_app import SecureTransferApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SecureTransferApp()
    window.show()
    sys.exit(app.exec_()) 