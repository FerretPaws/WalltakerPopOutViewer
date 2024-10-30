from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtGui import *
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *

class ImagePopOut(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.image_label = QtWidgets.QLabel(self)
        self.setWindowTitle("Image Pop-Out")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.is_moving = False

        # Set maximum dimensions for the pop-out image
        self.max_width = 800  # Set maximum width
        self.max_height = 600  # Set maximum height

    def update_image(self, pixmap):
        # Scale the pixmap to fit within the maximum dimensions while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(self.max_width, self.max_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.adjustSize()
        self.resize(self.image_label.size())

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_moving = True
            self.mouse_start_position = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton and self.is_moving:
            self.move(event.globalPos() - self.mouse_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.is_moving = False
