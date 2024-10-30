import sys
import requests
from PyQt5.QtWidgets import QMessageBox
from PIL import Image
from io import BytesIO
import threading
import time
import shelve
from PIL.ImageQt import ImageQt
from PyQt5.QtGui import *
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
from PyQt5.QtCore import QTimer
import pathlib
import pygame
from image_popout import ImagePopOut # type: ignore

class WalltakerApp(QtWidgets.QMainWindow):
    user_info_signal = QtCore.pyqtSignal(dict)
    image_signal = QtCore.pyqtSignal(QPixmap)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Walltaker Pop-Out Viewer")
        self.setFixedSize(500, 1000)
        self.bg_color = "#2E2E2E"
        self.text_color = "#FFFFFF"
        self.button_bg = "#555555"
        self.link_color = "#FFFFFF"

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QtWidgets.QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setAlignment(QtCore.Qt.AlignCenter)

        self.link_id = QtWidgets.QLineEdit()
        self.api_key = QtWidgets.QLineEdit()
        self.username = None
        self.image_link = None
        self.user_account_link = None

        self.toast_label = QLabel("")
        self.toast_label.setStyleSheet("background-color: #333; color: #fff; padding: 10px; border-radius: 5px; text-align: center;")
        self.layout.addWidget(self.toast_label)
        self.toast_label.hide()

        self.load_settings()
        self.create_entry_fields()
        self.create_response_buttons()
        self.create_custom_response_section()

        self.start_button = QtWidgets.QPushButton("Start")
        self.start_button.setStyleSheet(f"background-color: red; color: {self.text_color};")
        self.start_button.setFixedSize(100, 40)
        self.start_button.clicked.connect(self.start_polling)
        self.layout.addWidget(self.start_button, alignment=QtCore.Qt.AlignCenter)

        self.image_label = QtWidgets.QLabel()
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addWidget(self.image_label)

        self.user_info_frame = QtWidgets.QGroupBox("Setter Info")
        self.user_info_layout = QtWidgets.QVBoxLayout(self.user_info_frame)
        self.layout.addWidget(self.user_info_frame)

        self.user_info_signal.connect(self.display_user_info)
        self.image_signal.connect(self.update_image_label)

        self.polling_interval = 15
        self.is_polling = False

        self.setStyleSheet(f"background-color: {self.bg_color}; color: {self.text_color};")

        # Toggle Pop-Out Mode
        self.popout_toggle_button = QtWidgets.QPushButton("Enable Pop-Out Mode")
        self.popout_toggle_button.setCheckable(True)
        self.popout_toggle_button.clicked.connect(self.toggle_popout_mode)
        self.layout.addWidget(self.popout_toggle_button, alignment=QtCore.Qt.AlignCenter)

        # Initialize pop-out window
        self.popout_window = ImagePopOut()

        self.image_signal.connect(self.update_image_label)
        self.image_signal.connect(self.popout_window.update_image) 

        self.polling_delay_slider = QSlider(QtCore.Qt.Horizontal)
        self.polling_delay_slider.setMinimum(10)
        self.polling_delay_slider.setMaximum(60)
        self.polling_delay_slider.setValue(10)
        self.polling_delay_slider.valueChanged.connect(self.update_polling_delay)

        self.popout_size_slider = QSlider(QtCore.Qt.Horizontal)
        self.popout_size_slider.setMinimum(100)
        self.popout_size_slider.setMaximum(1000)
        self.popout_size_slider.setValue(500)
        self.popout_size_slider.valueChanged.connect(self.update_popout_size)

        self.notif_vol_slider = QSlider(QtCore.Qt.Horizontal)
        self.notif_vol_slider.setMinimum(0)
        self.notif_vol_slider.setMaximum(100)
        self.notif_vol_slider.setValue(30)
        self.notif_vol_slider.valueChanged.connect(self.update_notif_vol_timer)

        self.popout_size_timer = QTimer()
        self.popout_size_timer.timeout.connect(self.update_popout_size_timer)
        self.popout_size_timer.setSingleShot(True)
        self.popout_delay = 100  # 200ms delay

        self.polling_delay_timer = QTimer()
        self.polling_delay_timer.timeout.connect(self.update_polling_delay_timer)
        self.polling_delay_timer.setSingleShot(True)
        self.polling_delay = 100  # 200ms delay

        self.notif_vol_timer = QTimer()
        self.notif_vol_timer.timeout.connect(self.update_notif_vol_timer)
        self.notif_vol_timer.setSingleShot(True)
        self.notif_vol_delay = 100  # 200ms delay

        # Create labels to display the current values
        self.polling_delay_label = QLabel("Polling Delay (s): 10")
        self.layout.addWidget(self.polling_delay_label)
        self.layout.addWidget(self.polling_delay_slider)

        self.popout_size_label = QLabel("Pop-out Size: 500")
        self.layout.addWidget(self.popout_size_label)
        self.layout.addWidget(self.popout_size_slider)

        self.notif_vol_label = QLabel("Notification Volume: 30")
        self.layout.addWidget(self.notif_vol_label)
        self.layout.addWidget(self.notif_vol_slider)

        current_dir = pathlib.Path(__file__).parent

        # Create a relative path to the images folder
        images_folder = current_dir / 'images'

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(f'{images_folder}/WTPopOutIcon.png'))  # replace with your icon
        self.tray_icon.show()

        self.tray_menu = QMenu(self)
        self.tray_menu.addAction(QAction('Show', self, triggered=self.show))
        self.tray_menu.addAction(QAction('Exit', self, triggered=self.exit))
        self.tray_icon.setContextMenu(self.tray_menu)

    def show_toast(self, message, success=True):
        self.toast_label.setText(message)
        self.toast_label.setStyleSheet("background-color: #333; color: #fff; padding: 10px; border-radius: 5px;" if success else "background-color: #f00; color: #fff; padding: 10px; border-radius: 5px;")
        self.toast_label.show()
        QTimer.singleShot(3000, self.toast_label.hide)

    def create_entry_fields(self):
        link_id_label = QtWidgets.QLabel("Link ID:")
        link_id_label.setStyleSheet(f"color: {self.text_color};")
        self.layout.addWidget(link_id_label)
        self.link_id.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        self.layout.addWidget(self.link_id)

        api_key_label = QtWidgets.QLabel("API Key:")
        api_key_label.setStyleSheet(f"color: {self.text_color};")
        self.layout.addWidget(api_key_label)
        self.api_key.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        self.api_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.layout.addWidget(self.api_key)

    def create_response_buttons(self):

        current_dir = pathlib.Path(__file__).parent

        # Create a relative path to the images folder
        images_folder = current_dir / 'images'

        # Use the relative path to load the images

        emoji_files = [
            f"{images_folder}/emoji_heart.png",
            f"{images_folder}/emoji_water.png",
            f"{images_folder}/emoji_vomit.png",
            f"{images_folder}/emoji_thumbsup.png",
        ]
        emoji_texts = ["😍", "💦", "🤮", "👍"]
        emoji_types = ["horny", "came", "disgust", "ok"]

        response_layout = QtWidgets.QHBoxLayout()
        for i, (emoji_file, emoji_text, emoji_type) in enumerate(zip(emoji_files, emoji_texts, emoji_types)):
            button = QtWidgets.QPushButton()
            button.setIcon(QtGui.QIcon(emoji_file))
            button.setIconSize(QtCore.QSize(40, 40))
            button.clicked.connect(lambda checked, emoji=emoji_text, type_=emoji_type: self.send_response(emoji, type_))
            button.setFixedSize(60, 60)
            response_layout.addWidget(button)

        self.layout.addLayout(response_layout)

    def create_custom_response_section(self):
        custom_response_label = QtWidgets.QLabel("Custom Reply:")
        custom_response_label.setStyleSheet(f"color: {self.text_color};")
        self.layout.addWidget(custom_response_label)

        self.custom_response_entry = QtWidgets.QLineEdit()
        self.custom_response_entry.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        self.layout.addWidget(self.custom_response_entry)

        send_custom_button = QtWidgets.QPushButton("Send Reply")
        send_custom_button.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        send_custom_button.clicked.connect(self.send_custom_response)
        self.layout.addWidget(send_custom_button)

    def save_settings(self):
        with shelve.open("walltaker_settings") as settings:
            settings["link_id"] = self.link_id.text()
            settings["api_key"] = self.api_key.text()
            self.show_toast("Settings saved!")

    def fetch_user_info(self, username):
        api_key = self.api_key.text()
        if not api_key:
            self.show_toast("An API key is required!")
            return
            
        url = f"https://walltaker.joi.how/api/users/{username}.json?api_key={api_key}"
        headers = {"User-Agent": "WTPopOutViewer"}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            user_data = response.json()
            self.username = user_data['username']
            self.user_account_link = f"https://walltaker.joi.how/users/{self.username}"
            self.user_info_signal.emit(user_data)
        except Exception as e:
            self.show_toast("Error fetching user info: " + str(e))

    def display_user_info(self, user_data):
        for i in reversed(range(self.user_info_layout.count())): 
            widget = self.user_info_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        user_account_label = QtWidgets.QLabel(f"Set by <a href='{self.user_account_link}' style='color: {self.link_color}; text-decoration: underline;'>{self.username}</a>, they have set {user_data['set_count']} links")
        user_account_label.setOpenExternalLinks(True)
        user_account_label.setStyleSheet(f"color: {self.link_color};")

        self.user_info_layout.addWidget(user_account_label)
        self.user_info_layout.addWidget(QtWidgets.QLabel(f"{user_data['username']} {'is' if user_data['online'] else 'is not'} Online", self.user_info_frame))
        self.user_info_layout.addWidget(QtWidgets.QLabel(f"{user_data['username']} {'is your' if user_data['friend'] else 'is not your'} friend", self.user_info_frame))

        if self.image_link:
            image_link_label = QtWidgets.QLabel(f"Image Link: <a href='{self.image_link}' style='color: {self.link_color}; text-decoration: underline;'>{self.image_link}</a>")
            image_link_label.setOpenExternalLinks(True)
            self.user_info_layout.addWidget(image_link_label)

    def start_polling(self):
        if not self.link_id.text() or not self.api_key.text():
            self.show_toast("Please enter both Link ID and API key!")
            return

        self.username = None
        self.save_settings()
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("background-color: black; color: white;")
        self.is_polling = True
        threading.Thread(target=self.poll_data, daemon=True).start()

    def poll_data(self):
        last_posted_by = None
        last_post_url = None
        while self.is_polling:
            url = f"https://walltaker.joi.how/links/{self.link_id.text()}.json"
            headers = {"User-Agent": "WTPopOutViewer"}
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data['post_url'] != last_post_url:
                    last_posted_by = data['set_by']
                    self.image_link = data["post_url"]
                    last_post_url = self.image_link
                    self.fetch_user_info(data['set_by'])
                    print("Userinfo gathered")

                    image_response = requests.get(data["post_url"], headers=headers)
                    image = Image.open(BytesIO(image_response.content))
                    qt_image = ImageQt(image)
                    pixmap = QPixmap.fromImage(qt_image)
                    self.image_signal.emit(pixmap)  # Emit the signal with the new pixmap
            except Exception as e:
                self.show_error(f"Polling failed: {e}")
            time.sleep(self.polling_interval)

    def update_image_label(self, pixmap):
        max_width = self.central_widget.width() - 40  # subtract some padding
        max_height = self.central_widget.height() - 40  # subtract some padding

        scaled_pixmap = pixmap.scaled(max_width, max_height, QtCore.Qt.KeepAspectRatio)
        self.image_label.setPixmap(scaled_pixmap)
        if self.popout_toggle_button.isChecked():
            self.popout_window.update_image(pixmap)

        current_dir = pathlib.Path(__file__).parent

        # Create a relative path to the images folder
        sounds_folder = current_dir / 'sounds'
        print(sounds_folder)
        pygame.init()
        pygame.mixer.music.load(f"{sounds_folder}/notif.mp3")
        pygame.mixer.music.set_volume(self.notif_vol_slider.value() / 100)  # Set the volume to 50%
        pygame.mixer.music.play()


    def send_response(self, emoji, response_type):
        if self.username:
            url = f"https://walltaker.joi.how/api/links/{self.link_id.text()}/response.json"
            payload = {
                "api_key": self.api_key.text(),
                "type": response_type,
            }
            headers = {"User-Agent": "WTPopOutViewer"}
            try:
                response = requests.post(url, data=payload, headers=headers)
                response.raise_for_status()
                self.show_toast("Response sent!", success=True)
            except Exception as e:
                self.show_error(f"Response failed: {e}")

    def send_custom_response(self):
        custom_response = self.custom_response_entry.text()
        if self.username and custom_response:
            url = f"https://walltaker.joi.how/api/links/{self.link_id.text()}/response.json"
            payload = {
                "api_key": self.api_key.text(),
                "text": custom_response,
            }
            headers = {"User-Agent": "WTPopOutViewer"}
            try:
                response = requests.post(url, data=payload, headers=headers)
                response.raise_for_status()
                self.show_toast("Response sent!", success=True)
            except Exception as e:
                self.show_error(f"Response failed: {e}")

    def show_error(self, message):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setText(message)
        msg.setWindowTitle("Error")
        msg.exec_()

    def load_settings(self):
        with shelve.open("walltaker_settings") as settings:
            self.link_id.setText(settings.get("link_id", ""))
            self.api_key.setText(settings.get("api_key", ""))

    def closeEvent(self, event):
        self.is_polling = False
        event.accept()

    def toggle_popout_mode(self):
        if self.popout_toggle_button.isChecked():
            self.popout_toggle_button.setText("Disable Pop-Out Mode")
            self.popout_window.show()
        else:
            self.popout_toggle_button.setText("Enable Pop-Out Mode")
            self.popout_window.hide()
            
    def update_popout_size(self, value):
        self.popout_size_timer.stop()
        self.popout_size_timer.start(self.popout_delay)

    def update_popout_size_timer(self):
        # Put the original code from update_popout_size here
        self.popout_window.max_width = self.popout_size_slider.value()
        self.popout_window.max_height = self.popout_size_slider.value()
        if self.popout_toggle_button.isChecked():
            image_response = requests.get(self.image_link)
            image = Image.open(BytesIO(image_response.content))
            qt_image = ImageQt(image)
            pixmap = QPixmap.fromImage(qt_image)
            self.popout_window.update_image(pixmap)
        self.popout_size_label.setText(f"Pop-out Size: {self.popout_size_slider.value()}")

    def update_polling_delay(self, value):
        self.polling_delay_timer.stop()
        self.polling_delay_timer.start(self.polling_delay)

    def update_polling_delay_timer(self):
        # Put the original code from update_polling_delay here
        self.polling_interval = self.polling_delay_slider.value()
        self.polling_delay_label.setText(f"Polling Delay (s): {self.polling_interval}")

    def update_notif_vol_timer(self):
        # Put the original code from update_polling_delay here
        self.notif_vol_interval = self.notif_vol_slider.value()
        self.notif_vol_label.setText(f"Notification Volume: {self.notif_vol_interval}")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray_icon.showMessage('Walltaker', 'Running in background')

    def exit(self):
        self.is_polling = False
        self.popout_window.close()
        self.close()