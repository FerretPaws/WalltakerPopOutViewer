import requests
from PyQt5.QtWidgets import QMessageBox
from PIL import Image
from io import BytesIO
import threading
import time
from PIL.ImageQt import ImageQt
from PyQt5.QtGui import *
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import *
from PyQt5 import QtGui
from PyQt5.QtCore import QTimer
import pathlib
import pygame
import os
from image_popout import ImagePopOut # type: ignore
from settings import SettingsManager

class WalltakerApp(QtWidgets.QMainWindow):
    user_info_signal = QtCore.pyqtSignal(dict)
    image_signal = QtCore.pyqtSignal(QPixmap)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Walltaker Pop-Out Viewer")
        self.settings_manager = SettingsManager()

        self.base_width = 700
        self.base_height = 1000
        self.scale_window_to_screen()
        
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

        self.create_entry_fields()
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

        self.setStyleSheet(f"background-color: {self.bg_color}; color: {self.text_color}; font-size: 13pt; font-family: Helvetica;")

        settings_button_layout = QtWidgets.QHBoxLayout()

        self.popout_toggle_button = QtWidgets.QPushButton("Enable Pop-Out")
        self.popout_toggle_button.setCheckable(True)
        self.popout_toggle_button.clicked.connect(self.toggle_popout_mode)
        self.layout.addWidget(self.popout_toggle_button, alignment=QtCore.Qt.AlignCenter)
        self.popout_toggle_button.setStyleSheet(f"background-color: {self.button_bg}")

        self.download_button = QtWidgets.QPushButton("Download")
        self.download_button.clicked.connect(self.download_image)
        self.layout.addWidget(self.download_button, alignment=QtCore.Qt.AlignCenter)
        self.download_button.setStyleSheet(f"background-color: {self.button_bg}")

        self.auto_download_button = QtWidgets.QPushButton("Toggle Auto Download")
        self.auto_download_button.setCheckable(True)
        self.auto_download_button.clicked.connect(self.toggle_auto_download)
        self.layout.addWidget(self.auto_download_button, alignment=QtCore.Qt.AlignCenter)
        self.auto_download_button.setStyleSheet(f"background-color: {self.button_bg}")

        self.fade_out_button = QtWidgets.QPushButton("Fade Out Pop-Out Image")
        self.fade_out_button.setCheckable(True)
        self.fade_out_button.clicked.connect(self.toggle_fade_out)
        self.layout.addWidget(self.fade_out_button, alignment=QtCore.Qt.AlignCenter)
        self.fade_out_button.setStyleSheet(f"background-color: {self.button_bg}")

        # Add a new attribute to the WalltakerApp class to track the fade out state
        self.fade_out_enabled = False

        self.slider_toggle_button = QtWidgets.QPushButton("Edit Settings")
        self.slider_toggle_button.clicked.connect(self.toggle_sliders)
        self.layout.addWidget(self.slider_toggle_button)
        self.slider_toggle_button.setStyleSheet(f"background-color: {self.button_bg}")

        settings_button_layout.addWidget(self.popout_toggle_button)
        settings_button_layout.addWidget(self.download_button)
        settings_button_layout.addWidget(self.auto_download_button)
        settings_button_layout.addWidget(self.fade_out_button)
        # Add other buttons here
        self.layout.addLayout(settings_button_layout)

        # Initialize pop-out window
        self.popout_window = ImagePopOut()

        self.image_signal.connect(self.update_image_label)
        self.image_signal.connect(self.popout_window.update_image)

        # Sliders and Labels
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

        self.image_signal.connect(self.reset_popout_opacity)
        self.image_signal.connect(self.update_image_label)
        self.image_signal.connect(self.toggle_fade_out)
        self.image_signal.connect(self.popout_window.update_image)

        self.load_settings()

        self.notif_vol_slider.hide()
        self.polling_delay_slider.hide()
        self.popout_size_slider.hide()
        self.fade_out_button.hide()
        self.auto_download_button.hide()

    def show_toast(self, message, success=True):
        self.toast_label.setText(message)
        self.toast_label.setStyleSheet("background-color: #228B22; color: #fff; padding: 10px; border-radius: 5px" if success else "background-color: #00FF00; color: #fff; padding: 10px; border-radius: 5px")
        self.toast_label.show()
        QTimer.singleShot(3000, self.toast_label.hide)

    def toggle_sliders(self):
        if self.notif_vol_slider.isHidden():
            self.notif_vol_slider.show()
            self.polling_delay_slider.show()
            self.popout_size_slider.show()
            self.fade_out_button.show()
            self.auto_download_button.show()
            self.slider_toggle_button.setText("Hide Settings")

            # Show the labels and input fields
            for i in reversed(range(self.layout.count())):
                widget = self.layout.itemAt(i).widget()
                if isinstance(widget, QtWidgets.QLabel) and (widget.text() == "Link ID:" or widget.text() == "API Key:"):
                    widget.show()
                elif isinstance(widget, QtWidgets.QLineEdit) and (widget == self.link_id or widget == self.api_key):
                    widget.show()
        else:
            self.notif_vol_slider.hide()
            self.polling_delay_slider.hide()
            self.popout_size_slider.hide()
            self.fade_out_button.hide()
            self.auto_download_button.hide()
            self.slider_toggle_button.setText("Show Settings")

            # Hide the labels and input fields
            for i in reversed(range(self.layout.count())):
                widget = self.layout.itemAt(i).widget()
                if isinstance(widget, QtWidgets.QLabel) and (widget.text() == "Link ID:" or widget.text() == "API Key:"):
                    widget.hide()
                elif isinstance(widget, QtWidgets.QLineEdit) and (widget == self.link_id or widget == self.api_key):
                    widget.hide()

    def reset_popout_opacity(self):
        if self.popout_window.isVisible():
            self.popout_window.setWindowOpacity(1.0)  # reset opacity to 1.0

    def toggle_fade_out(self):
        self.fade_out_enabled = self.fade_out_button.isChecked()
        if self.fade_out_enabled:
            self.fade_out_timer = QTimer()
            self.fade_out_timer.timeout.connect(self.fade_out_popout)
            self.fade_out_timer.start(10000)  # 10 seconds
        else:
            self.reset_popout_opacity()

    # Define the fade_out_popout method
    def fade_out_popout(self):
        if self.popout_window.isVisible():
            self.popout_window.setWindowOpacity(0.1)  # fade out to 10% opacity
            self.fade_out_timer.stop()

    def toggle_auto_download(self):
        self.auto_download_images = self.auto_download_button.isChecked()
        self.save_settings()

    def download_image(self):  # sourcery skip: extract-method
        if self.image_link:
            response = requests.get(self.image_link)
            if response.status_code == 200:
                # Create the "downloads" folder if it doesn't exist
                downloads_folder = 'downloads'
                if not os.path.exists(downloads_folder):
                    os.makedirs(downloads_folder)

                # Get the number of existing images in the "downloads" folder
                existing_images = [f for f in os.listdir(downloads_folder) if f.startswith('img') and f.endswith('.png')]
                image_number = len(existing_images) + 1

                # Save the image inside the "downloads" folder with a unique file name
                image_path = os.path.join(downloads_folder, f'img_{image_number}.png')
                with open(image_path, 'wb') as f:
                    f.write(response.content)
                self.show_toast("Image downloaded!", success=True)
            else:
                self.show_toast("Download Failed!", success=False)
        else:
                self.show_toast("No image link!", success=False)

    def scale_window_to_screen(self):
        # Get screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()

        # Calculate scaling factor based on screen size and base dimensions
        scale_factor = min(screen_width / self.base_width, screen_height / self.base_height)

        # Apply scaling factor with slight reduction in height to set window size
        adjusted_height = int(self.base_height * scale_factor * .90) 
        self.setMinimumSize(int(self.base_width * scale_factor), adjusted_height)

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
        
    def create_custom_response_section(self):
        # Initialize and style custom response label
        custom_response_label = QtWidgets.QLabel("Reply:")
        custom_response_label.setStyleSheet(f"color: {self.text_color};")
        self.layout.addWidget(custom_response_label)

        # Layout for custom response input
        response_input_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(response_input_layout)

        # Input field for custom response text
        self.custom_response_entry = QtWidgets.QLineEdit()
        self.custom_response_entry.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        response_input_layout.addWidget(self.custom_response_entry)

        # Combo box for response types
        self.response_type_combo = QtWidgets.QComboBox()
        self.response_type_combo.addItems(["😍", "💦", "🤮", "👍"])  # Add more types if needed
        self.response_type_combo.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        self.response_type_combo.setFixedSize(50, 40)  # Set smaller size for combo box
        response_input_layout.addWidget(self.response_type_combo)

        # Button to send the custom reply
        send_custom_button = QtWidgets.QPushButton("Send Reply")
        send_custom_button.setStyleSheet(f"background-color: {self.button_bg}; color: {self.text_color};")
        send_custom_button.clicked.connect(lambda: self.send_custom_response(self.response_type_combo.currentText(), self.custom_response_entry.text()))
        self.layout.addWidget(send_custom_button)

    def send_custom_response(self, response_type, custom_response):
        response_type_map = {
            "😍": "horny",
            "💦": "came",
            "🤮": "disgust",
            "👍": "ok",
        }
        actual_response_type = response_type_map.get(response_type, "ok")

        # Ensure link_id and api_key are set
        if not self.link_id or not self.api_key or not self.link_id.text() or not self.api_key.text():
            print("Debug: Missing Link ID or API Key.")
            self.show_error("Link ID or API Key is missing.")
            return

        # Construct URL and payload
        url = f"https://walltaker.joi.how/api/links/{self.link_id.text()}/response.json"
        payload = {
            "api_key": self.api_key.text(),
            "type": actual_response_type,
            "text": custom_response if custom_response else response_type,
        }
        headers = {"User-Agent": "WTPopOutViewer"}

        print(f"Debug: Sending request with URL - {url}, Payload - {payload}")  # Before sending request

        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()

            # Comment out show_toast and check if crash still happens
            print("Debug: Response sent successfully")
            self.show_toast("Response sent!", success=True)  # Uncomment after testing
        except requests.exceptions.RequestException as req_err:
            print(f"Debug: Request error occurred: {req_err}")
            self.show_error(f"Request error occurred: {req_err}")  # Uncomment after testing
        except Exception as e:
            print(f"Debug: Unexpected error: {e}")
            self.show_error(f"Unexpected error: {e}")  # Uncomment after testing

        print("Debug: End of send_custom_response")

    def save_settings(self):
        self.settings_manager.save_settings(
            self.link_id.text(),
            self.api_key.text(),
            self.polling_delay_slider.value(),
            self.popout_size_slider.value(),
            self.notif_vol_slider.value(),
            self.auto_download_button.isChecked(),
            self.fade_out_button.isChecked(),
        )

    def fetch_user_info(self, username):
        api_key = self.api_key.text()
        if not api_key:
            self.show_toast("An API key is required!", success=False)
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
            self.show_toast("Error fetching user info: " + str(e), success=False)

    def display_user_info(self, user_data):
        for i in reversed(range(self.user_info_layout.count())): 
            widget = self.user_info_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        user_account_label = QtWidgets.QLabel(f"Set by <a href='{self.user_account_link}' style='color: {self.link_color}; text-decoration: underline;'>{self.username}</a>, they have set {user_data['set_count']} links")
        user_account_label.setOpenExternalLinks(True)
        user_account_label.setStyleSheet(f"color: {self.link_color};")

        if 'friend' in user_data:
            self.user_info_layout.addWidget(user_account_label)
            self.user_info_layout.addWidget(QtWidgets.QLabel(f"{user_data['username']} {'is' if user_data['online'] else 'is not'} Online", self.user_info_frame))
            self.user_info_layout.addWidget(QtWidgets.QLabel(f"{user_data['username']} {'is your' if user_data['friend'] else 'is not your'} friend (CURRENTLY BROKEN)", self.user_info_frame))

            if self.image_link:
                image_link_label = QtWidgets.QLabel(f"Image Link: <a href='{self.image_link}' style='color: {self.link_color}; text-decoration: underline;'>{self.image_link}</a>")
                image_link_label.setOpenExternalLinks(True)
                self.user_info_layout.addWidget(image_link_label)
        else:
            self.user_info_layout.addWidget(user_account_label)
            self.user_info_layout.addWidget(QtWidgets.QLabel(f"{user_data['username']} {'is' if user_data['online'] else 'is not'} Online", self.user_info_frame))
            self.user_info_layout.addWidget(QtWidgets.QLabel(f"Your account has not been updated! Contact the staff team!", self.user_info_frame))

            if self.image_link:
                image_link_label = QtWidgets.QLabel(f"Image Link: <a href='{self.image_link}' style='color: {self.link_color}; text-decoration: underline;'>{self.image_link}</a>")
                image_link_label.setOpenExternalLinks(True)
                self.user_info_layout.addWidget(image_link_label)

    def start_polling(self):
        if not self.link_id.text() or not self.api_key.text():
            self.show_toast("Please enter both Link ID and API key!", success=False)
            return

        self.username = None
        self.save_settings()
        self.start_button.setEnabled(False)
        self.start_button.setStyleSheet("background-color: black; color: white;")
        self.is_polling = True

        # Hide the labels and input fields
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QtWidgets.QLabel) and (widget.text() == "Link ID:" or widget.text() == "API Key:"):
                widget.hide()
            elif isinstance(widget, QtWidgets.QLineEdit) and (widget == self.link_id or widget == self.api_key):
                widget.hide()

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
                    # Check for unsupported file types
                    if data['post_url'].endswith(('.mp4', '.gif', '.webm')):
                        self.show_toast("Unsupported media format received (.mp4, .gif, .webm). Keeping the previous image.", success=False)
                    else:
                        last_posted_by = data['set_by']
                        self.image_link = data["post_url"]
                        last_post_url = self.image_link
                        self.fetch_user_info(data['set_by'])

                        # Attempt to load and display the image
                        image_response = requests.get(data["post_url"], headers=headers)
                        image = Image.open(BytesIO(image_response.content))
                        qt_image = ImageQt(image)
                        pixmap = QPixmap.fromImage(qt_image)
                        self.image_signal.emit(pixmap)  # Emit the signal with the new pixmap
                        self.toast_label.hide()
                        # Auto-download feature
                        if self.auto_download_button.isChecked() and self.image_link:
                            self.download_image()

            except Exception as e:
                self.show_toast(f"Polling failed: {e}", success=False)

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
        pygame.init()
        pygame.mixer.music.load(f"{sounds_folder}/notif.mp3")
        pygame.mixer.music.set_volume(self.notif_vol_slider.value() / 100)  # Set the volume to 50%
        pygame.mixer.music.play()

    def toggle_popout_mode(self):
        if self.popout_toggle_button.isChecked():
            self.popout_toggle_button.setText("Disable Pop-Out Mode")
            self.popout_window.show()
        else:
            self.popout_toggle_button.setText("Enable Pop-Out Mode")
            self.popout_window.hide()
        self.save_settings()
            
    def update_popout_size(self, value):
        self.popout_size_timer.stop()
        self.popout_size_timer.start(self.popout_delay)
        self.save_settings()

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
        self.save_settings()

    def update_polling_delay_timer(self):
        # Put the original code from update_polling_delay here
        self.polling_interval = self.polling_delay_slider.value()
        self.polling_delay_label.setText(f"Polling Delay (s): {self.polling_interval}")

    def update_notif_vol_timer(self):
        # Put the original code from update_polling_delay here
        self.notif_vol_interval = self.notif_vol_slider.value()
        self.notif_vol_label.setText(f"Notification Volume: {self.notif_vol_interval}")
        self.save_settings()

    def load_settings(self):
        settings = self.settings_manager.load_settings()
        self.link_id.setText(settings["link_id"])
        self.api_key.setText(settings["api_key"])
        self.polling_delay_slider.setValue(settings["polling_delay"])
        self.popout_size_slider.setValue(settings["popout_size"])
        self.notif_vol_slider.setValue(settings["notif_vol"])
        self.auto_download_button.setChecked(settings["auto_download"])
        self.fade_out_button.setChecked(settings["fade_out"])

    def closeEvent(self, event):
        if self.is_polling:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage('Walltaker', 'Running in background')
        else:
            event.accept()

    def exit(self):
        self.is_polling = False
        self.popout_window.close()
        self.tray_icon.showMessage('Walltaker', 'Closing...')
        self.close()
