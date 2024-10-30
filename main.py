import sys
from PyQt5 import QtWidgets, QtCore
from walltaker_app import WalltakerApp # type: ignore

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = WalltakerApp()
    window.show()
    sys.exit(app.exec_())