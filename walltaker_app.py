import requests
import json
from urllib.parse import urlparse
from PIL import Image
from io import BytesIO
import threading
import gc
import time
from PyQt5 import QtGui
from PyQt5.QtGui import QImage, QPixmap, QIcon, QPainter, QPen, QPalette, QMovie
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QAction, QCheckBox, QComboBox, QDockWidget, QFrame, QHBoxLayout, QLabel,
    QMenu, QPushButton, QScrollArea, QSlider, QSystemTrayIcon, QToolBar,
    QToolButton, QVBoxLayout, QWidget,
)
from PyQt5.QtCore import QTimer, QPointF
import pathlib
import pygame
import os
from image_popout import ImagePopOut
from media import MediaCache, VideoPlayer, media_kind
from settings import SettingsManager
from services import SERVICES, DEFAULT_SERVICE, CUSTOM_SERVICE, CLIENT_NAME, get_service
from theme import THEMES, build_stylesheet
import datetime

try:
    import websocket
except ImportError:
    websocket = None

UNSUPPORTED_MESSAGE = "GIF/video received. Enable GIFs & videos under Behaviour to view it. Keeping the previous image."


MAX_IMAGE_EDGE = 3840


def ImageQt(image):
    image = image.convert("RGBA")
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, image.width, image.height, image.width * 4, QImage.Format_RGBA8888)
    return qimage.copy()


def decode_pixmap(content):
    with Image.open(BytesIO(content)) as image:
        if max(image.size) > MAX_IMAGE_EDGE:
            image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
        return QPixmap.fromImage(ImageQt(image))


class ViewportLabel(QLabel):
    clicked = QtCore.pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PlaybackIndicator(QWidget):
    """Round badge drawn over the viewport: ▶ while playing, ❚❚ while paused, ↻ when the video has ended."""

    SIZE = 72

    def __init__(self, parent):
        super().__init__(parent)
        self.mode = "playing"
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)
        self.hide()

    def show_mode(self, mode, flash_ms=0):
        self.mode = mode
        self.hide_timer.stop()
        self.update()
        self.show()
        self.raise_()
        if flash_ms:
            self.hide_timer.start(flash_ms)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 150))
        painter.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        painter.setBrush(QtGui.QColor(255, 255, 255, 235))
        c, s = self.SIZE / 2, self.SIZE
        if self.mode == "playing":
            painter.drawPolygon(QtGui.QPolygonF([QPointF(c - s * 0.12, c - s * 0.2),
                                                 QPointF(c - s * 0.12, c + s * 0.2),
                                                 QPointF(c + s * 0.22, c)]))
        elif self.mode == "paused":
            bar_w, bar_h = s * 0.1, s * 0.38
            painter.drawRoundedRect(QtCore.QRectF(c - s * 0.15, c - bar_h / 2, bar_w, bar_h), 2, 2)
            painter.drawRoundedRect(QtCore.QRectF(c + s * 0.05, c - bar_h / 2, bar_w, bar_h), 2, 2)
        else:
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QPen(QtGui.QColor(255, 255, 255, 235), s * 0.07, cap=QtCore.Qt.RoundCap))
            radius = s * 0.2
            painter.drawArc(QtCore.QRectF(c - radius, c - radius, radius * 2, radius * 2), 40 * 16, 290 * 16)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(255, 255, 255, 235))
            tip = QPointF(c + radius * 0.77 + s * 0.05, c - radius * 0.64 - s * 0.01)
            painter.drawPolygon(QtGui.QPolygonF([tip + QPointF(s * 0.09, s * 0.02), tip + QPointF(-s * 0.04, -s * 0.08),
                                                 tip + QPointF(-s * 0.05, s * 0.09)]))
        painter.end()


class NoScrollSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


def transport_icon(kind, color, disabled_color, size=11):
    """Small crisp play/pause icon painted in the given colours (normal and disabled)."""
    icon = QIcon()
    for mode, fill in ((QIcon.Normal, color), (QIcon.Disabled, disabled_color)):
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.setDevicePixelRatio(2)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(fill))
        if kind == "pause":
            bar = size * 0.26
            painter.drawRoundedRect(QtCore.QRectF(size * 0.14, size * 0.1, bar, size * 0.8), 1.2, 1.2)
            painter.drawRoundedRect(QtCore.QRectF(size * 0.6, size * 0.1, bar, size * 0.8), 1.2, 1.2)
        else:
            painter.drawPolygon(QtGui.QPolygonF([QPointF(size * 0.2, size * 0.08),
                                                 QPointF(size * 0.2, size * 0.92),
                                                 QPointF(size * 0.9, size * 0.5)]))
        painter.end()
        icon.addPixmap(pixmap, mode)
    return icon


class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.palette().color(QPalette.Text), 1.6, cap=QtCore.Qt.RoundCap, join=QtCore.Qt.RoundJoin))
        cx, cy = self.width() - 13, self.height() / 2
        painter.drawPolyline(QPointF(cx - 3.5, cy - 1.5), QPointF(cx, cy + 2), QPointF(cx + 3.5, cy - 1.5))
        painter.end()


class CollapsibleSection(QWidget):
    def __init__(self, title, expanded=True, parent=None):
        super().__init__(parent)
        self.header = QToolButton()
        self.header.setObjectName("sectionHeader")
        self.header.setText(title)
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.header.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.header.toggled.connect(self._on_toggled)

        self.body = QFrame()
        self.body.setObjectName("sectionBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 10, 10, 10)
        self.body_layout.setSpacing(8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.body)
        self._on_toggled(expanded)

    def _on_toggled(self, expanded):
        self.header.setArrowType(QtCore.Qt.DownArrow if expanded else QtCore.Qt.RightArrow)
        self.body.setVisible(expanded)

    def add_widget(self, widget):
        self.body_layout.addWidget(widget)

    def add_layout(self, layout):
        self.body_layout.addLayout(layout)


class TitleBar(QWidget):
    def __init__(self, window, title, icon, resizable=True):
        super().__init__(window)
        self.host = window
        self.resizable = resizable
        self.drag_origin = None
        self.dragging = False
        if not hasattr(window, "snap_restore"):
            window.snap_restore = None
            window.snap_target = None
        self.setObjectName("titleBar")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(16, 16))
        icon_label.setFixedSize(20, 32)
        layout.addWidget(icon_label)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleText")
        layout.addWidget(self.title_label)
        layout.addStretch(1)

        self.max_button = None
        if resizable:
            layout.addWidget(self._button("\uE921", "titleButton", window.showMinimized))
            self.max_button = self._button("\uE922", "titleButton", self.toggle_maximized)
            layout.addWidget(self.max_button)
        layout.addWidget(self._button("\uE8BB", "titleClose", window.close))
        self.setFixedHeight(32)

    @staticmethod
    def _button(glyph, name, slot):
        button = QToolButton()
        button.setObjectName(name)
        button.setText(glyph)
        button.setFixedSize(46, 32)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        button.clicked.connect(lambda *_: slot())
        return button

    def toggle_maximized(self):
        if self.host.isMaximized():
            self.host.showNormal()
        else:
            self.host.showMaximized()

    def sync_state(self):
        if self.max_button is not None:
            self.max_button.setText("\uE923" if self.host.isMaximized() else "\uE922")

    SNAP_MARGIN = 8

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_origin = event.globalPos()
            self.drag_start_pos = self.host.pos()
            self.dragging = False

    def mouseMoveEvent(self, event):
        if getattr(self, "drag_origin", None) is None or not (event.buttons() & QtCore.Qt.LeftButton):
            return
        host = self.host
        if not self.dragging:
            if (event.globalPos() - self.drag_origin).manhattanLength() < 4:
                return
            self.dragging = True
            snapped = host.snap_restore is not None and host.geometry() == host.snap_target
            if host.isMaximized() or snapped:
                if host.isMaximized():
                    size = host.normalGeometry().size()
                    host.showNormal()
                else:
                    size = host.snap_restore.size()
                host.snap_restore = None
                cursor = event.globalPos()
                top_left = QtCore.QPoint(cursor.x() - size.width() // 2, cursor.y() - self.height() // 2)
                host.setGeometry(QtCore.QRect(top_left, size))
                self.drag_start_pos = top_left
                self.drag_origin = cursor
        host.move(self.drag_start_pos + event.globalPos() - self.drag_origin)

    def mouseReleaseEvent(self, event):
        was_dragging = self.dragging
        self.drag_origin = None
        self.dragging = False
        if event.button() != QtCore.Qt.LeftButton or not was_dragging or not self.resizable:
            return
        screen = QtWidgets.QApplication.screenAt(event.globalPos())
        if screen is None:
            return
        area = screen.availableGeometry()
        pos = event.globalPos()
        host = self.host
        margin = self.SNAP_MARGIN
        if pos.y() <= area.top() + margin:
            host.showMaximized()
            return
        if pos.x() <= area.left() + margin:
            target = QtCore.QRect(area.left(), area.top(), area.width() // 2, area.height())
        elif pos.x() >= area.right() - margin:
            half = area.width() // 2
            target = QtCore.QRect(area.right() + 1 - half, area.top(), half, area.height())
        else:
            return
        host.snap_restore = QtCore.QRect(host.geometry())
        host.setGeometry(target)
        host.snap_target = QtCore.QRect(host.geometry())

    def mouseDoubleClickEvent(self, event):
        if self.resizable and event.button() == QtCore.Qt.LeftButton:
            self.toggle_maximized()


class CameDialog(QtWidgets.QDialog):
    def __init__(self, parent, username, icon):
        super().__init__(parent)
        self.setObjectName("themedDialog")
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setModal(True)
        self.setMinimumWidth(380)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self, "Confirm", icon, resizable=False))

        body = QVBoxLayout()
        body.setContentsMargins(16, 14, 16, 14)
        body.setSpacing(10)
        question = QLabel(
            f"Let {username} know you came?\n"
            "This adds an orgasm to their profile and can't be undone."
        )
        question.setWordWrap(True)
        body.addWidget(question)
        hint = QLabel("Message (optional, leave blank for \"I came!~\")")
        hint.setObjectName("muted")
        body.addWidget(hint)
        self.entry = QtWidgets.QLineEdit()
        self.entry.returnPressed.connect(self.accept)
        body.addWidget(self.entry)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        send = QPushButton("Send")
        send.setObjectName("primary")
        send.setDefault(True)
        send.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(send)
        buttons.addWidget(cancel)
        body.addLayout(buttons)
        outer.addLayout(body)

    def message(self):
        return self.entry.text().strip() or "I came!~"


class EdgeGrip(QWidget):
    SIZE = 6

    def __init__(self, window, edges, cursor):
        super().__init__(window)
        self.host = window
        self.edges = edges
        self.setCursor(cursor)
        self.origin = None
        self.start = None

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.origin = event.globalPos()
            self.start = self.host.geometry()

    def mouseMoveEvent(self, event):
        if self.origin is None:
            return
        delta = event.globalPos() - self.origin
        geo = QtCore.QRect(self.start)
        min_w, min_h = self.host.minimumWidth(), self.host.minimumHeight()
        if self.edges & QtCore.Qt.LeftEdge:
            geo.setLeft(min(geo.left() + delta.x(), geo.right() - min_w + 1))
        if self.edges & QtCore.Qt.RightEdge:
            geo.setRight(max(geo.right() + delta.x(), geo.left() + min_w - 1))
        if self.edges & QtCore.Qt.TopEdge:
            geo.setTop(min(geo.top() + delta.y(), geo.bottom() - min_h + 1))
        if self.edges & QtCore.Qt.BottomEdge:
            geo.setBottom(max(geo.bottom() + delta.y(), geo.top() + min_h - 1))
        self.host.setGeometry(geo)

    def mouseReleaseEvent(self, event):
        self.origin = None


class WalltakerApp(QtWidgets.QMainWindow):
    user_info_signal = QtCore.pyqtSignal(dict)
    image_signal = QtCore.pyqtSignal(QPixmap)
    toast_signal = QtCore.pyqtSignal(str, bool)
    status_signal = QtCore.pyqtSignal(str)
    response_signal = QtCore.pyqtSignal(object, object)
    media_signal = QtCore.pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Walltaker Pop-Out Viewer")
        self.settings_manager = SettingsManager()
        self.resize(1100, 720)
        self.setMinimumSize(760, 520)

        current_dir = pathlib.Path(__file__).parent
        images_folder = current_dir / 'images'
        self.setWindowIcon(QIcon(str(images_folder / 'WTPopOutIcon.png')))
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.FramelessWindowHint)
        self.title_bar = TitleBar(self, "Walltaker Pop-Out Viewer", self.windowIcon())
        self.setMenuWidget(self.title_bar)

        self.theme_name = "Dark"
        self.link_color = THEMES[self.theme_name]["link"]
        self.username = None
        self.image_link = None
        self.image_backup_link = None
        self.numeric_link_id = None
        self.ws = None
        self.user_account_link = None
        self.current_pixmap = None
        self.polling_interval = 15
        self.is_polling = False
        self.fade_out_enabled = False
        self.fade_out_num = 10
        self.popout_delay = 100
        self.polling_delay = 100

        self.service_combo = NoScrollComboBox()
        for service in SERVICES.values():
            self.service_combo.addItem(service.label, service.key)
        self.service_combo.addItem("Custom…", CUSTOM_SERVICE)
        self.service_combo.currentIndexChanged.connect(self.on_service_changed)

        self.custom_host = QtWidgets.QLineEdit()
        self.custom_host.setPlaceholderText("e.g. walltaker.example.com")
        self.custom_host.editingFinished.connect(self.save_settings)
        self.custom_mode_combo = NoScrollComboBox()
        self.custom_mode_combo.addItem("Live (WebSocket)", True)
        self.custom_mode_combo.addItem("Polling (HTTP)", False)
        self.custom_mode_combo.currentIndexChanged.connect(self.update_polling_visibility)
        self.custom_mode_combo.currentIndexChanged.connect(self.save_settings)
        self.custom_widgets = QWidget()
        custom_layout = QVBoxLayout(self.custom_widgets)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(8)
        custom_layout.addWidget(self.field_label("Custom host (HTTPS/WSS)"))
        custom_layout.addWidget(self.custom_host)
        custom_layout.addWidget(self.field_label("Protocol"))
        custom_layout.addWidget(self.custom_mode_combo)

        self.link_id = QtWidgets.QLineEdit()
        self.link_id.setPlaceholderText("e.g. 1234")
        self.api_key = QtWidgets.QLineEdit()
        self.api_key.setPlaceholderText("Your Walltaker API key")
        self.api_key.setEchoMode(QtWidgets.QLineEdit.Password)

        self.popout_window = ImagePopOut()

        self.media_enabled = False
        self.media_cache = MediaCache()
        self.media_path = None
        self.movie = None
        self.player = VideoPlayer(self)
        self.player.frame_ready.connect(self.on_video_frame)
        self.player.error.connect(self.on_player_error)
        self.player.state_changed.connect(self.on_playback_state)

        self.build_viewport()
        self.build_toolbar()
        self.build_side_panel()
        self.build_status_bar()
        self.build_tray(images_folder)

        self.user_info_signal.connect(self.display_user_info)
        self.toast_signal.connect(self._show_toast)
        self.status_signal.connect(self.set_status)
        self.response_signal.connect(self.show_sent_response)
        self.media_signal.connect(self.show_media)
        self.image_signal.connect(self.stop_media)
        self.image_signal.connect(self.update_image_label)
        self.image_signal.connect(self.popout_window.update_image)
        self.image_signal.connect(self.reset_popout_opacity)
        self.image_signal.connect(self.toggle_fade_out)

        self.popout_size_timer = QTimer()
        self.popout_size_timer.timeout.connect(self.update_popout_size_timer)
        self.popout_size_timer.setSingleShot(True)

        self.polling_delay_timer = QTimer()
        self.polling_delay_timer.timeout.connect(self.update_polling_delay_timer)
        self.polling_delay_timer.setSingleShot(True)

        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.write_settings)

        self.smooth_render_timer = QTimer()
        self.smooth_render_timer.setSingleShot(True)
        self.smooth_render_timer.timeout.connect(self.render_viewport_pixmap)

        self.fade_out_timer = QTimer()
        self.fade_out_timer.setSingleShot(True)
        self.fade_out_timer.timeout.connect(self.fade_out_popout)
        self.audio_ready = False

        self.load_settings()
        self.edge_grips = {
            name: EdgeGrip(self, edges, cursor)
            for name, edges, cursor in (
                ("left", QtCore.Qt.LeftEdge, QtCore.Qt.SizeHorCursor),
                ("right", QtCore.Qt.RightEdge, QtCore.Qt.SizeHorCursor),
                ("top", QtCore.Qt.TopEdge, QtCore.Qt.SizeVerCursor),
                ("bottom", QtCore.Qt.BottomEdge, QtCore.Qt.SizeVerCursor),
                ("topleft", QtCore.Qt.LeftEdge | QtCore.Qt.TopEdge, QtCore.Qt.SizeFDiagCursor),
                ("topright", QtCore.Qt.RightEdge | QtCore.Qt.TopEdge, QtCore.Qt.SizeBDiagCursor),
                ("bottomleft", QtCore.Qt.LeftEdge | QtCore.Qt.BottomEdge, QtCore.Qt.SizeBDiagCursor),
                ("bottomright", QtCore.Qt.RightEdge | QtCore.Qt.BottomEdge, QtCore.Qt.SizeFDiagCursor),
            )
        }
        self.layout_edge_grips()
        self.apply_theme("Dark")

    def build_viewport(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)

        self.image_label = ViewportLabel("No image yet\nEnter your Link ID and API key, then press Start")
        self.image_label.clicked.connect(self.toggle_video_playback)
        self.image_label.setObjectName("viewport")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumSize(1, 1)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        layout.addWidget(self.image_label)

        self.toast_label = QLabel("", self.image_label)
        self.toast_label.setObjectName("toast")
        self.toast_label.setWordWrap(True)
        self.toast_label.hide()

        self.playback_indicator = PlaybackIndicator(self.image_label)

        self.setCentralWidget(container)

    def build_toolbar(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.addToolBar(toolbar)

        self.start_action = QAction("▶  Start", self)
        self.start_action.setToolTip("Begin polling the link")
        self.start_action.triggered.connect(self.start_polling)
        toolbar.addAction(self.start_action)

        toolbar.addSeparator()

        self.play_action = QAction("Play", self)
        self.play_action.setToolTip("Play or pause the current video (or click the viewport)")
        self.play_action.setEnabled(False)
        self.play_action.triggered.connect(self.toggle_video_playback)
        toolbar.addAction(self.play_action)
        self.toolbar = toolbar

        toolbar.addSeparator()

        self.download_action = QAction("⤓  Download", self)
        self.download_action.setToolTip("Save the current image, GIF or video")
        self.download_action.triggered.connect(self.download_image)
        toolbar.addAction(self.download_action)

        self.popout_action = QAction("⧉  Pop-Out", self)
        self.popout_action.setCheckable(True)
        self.popout_action.setToolTip("Show the image in a floating window")
        self.popout_action.triggered.connect(self.toggle_popout_mode)
        toolbar.addAction(self.popout_action)

    def build_side_panel(self):
        body = QWidget()
        body.setObjectName("panelBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        connection = CollapsibleSection("Connection")
        connection.add_widget(self.field_label("Service"))
        connection.add_widget(self.service_combo)
        connection.add_widget(self.custom_widgets)
        connection.add_widget(self.field_label("Link ID"))
        connection.add_widget(self.link_id)
        connection.add_widget(self.field_label("API Key"))
        connection.add_widget(self.api_key)
        layout.addWidget(connection)

        reply = CollapsibleSection("Reply")
        self.custom_response_entry = QtWidgets.QLineEdit()
        self.custom_response_entry.setPlaceholderText("Write a reply…")
        self.custom_response_entry.returnPressed.connect(self.on_send_clicked)
        self.response_type_combo = NoScrollComboBox()
        self.response_type_combo.addItems(["😍", "🤮", "👍"])
        self.response_type_combo.setFixedWidth(64)
        row = QHBoxLayout()
        row.addWidget(self.custom_response_entry)
        row.addWidget(self.response_type_combo)
        reply.add_layout(row)
        self.send_custom_button = QPushButton("Send Reply")
        self.send_custom_button.setObjectName("primary")
        self.send_custom_button.clicked.connect(self.on_send_clicked)
        reply.add_widget(self.send_custom_button)
        layout.addWidget(reply)

        self.came_button = QPushButton("💦  I came!~")
        self.came_button.setToolTip("Sends a \"Came\" response to whoever set your wallpaper")
        self.came_button.clicked.connect(self.on_came_clicked)
        reply.add_widget(self.came_button)

        self.sent_response_label = QLabel("")
        self.sent_response_label.setObjectName("muted")
        self.sent_response_label.setWordWrap(True)
        self.sent_response_label.hide()
        reply.add_widget(self.sent_response_label)

        info = CollapsibleSection("Setter Info")
        self.user_info_layout = info.body_layout
        placeholder = QLabel("Nothing yet.")
        placeholder.setObjectName("muted")
        info.add_widget(placeholder)
        layout.addWidget(info)

        popout = CollapsibleSection("Pop-Out Window", expanded=False)
        self.popout_toggle_button = QPushButton("Enable Pop-Out Mode")
        self.popout_toggle_button.setCheckable(True)
        self.popout_toggle_button.clicked.connect(self.toggle_popout_mode)
        popout.add_widget(self.popout_toggle_button)

        self.popout_size_slider = self.make_slider(100, 1000, 500, self.update_popout_size)
        self.popout_size_label = QLabel("500px")
        popout.add_layout(self.slider_row("Size", self.popout_size_slider, self.popout_size_label))

        self.fade_out_button = QCheckBox("Fade out after 10 seconds")
        self.fade_out_button.clicked.connect(self.toggle_fade_out)
        popout.add_widget(self.fade_out_button)

        self.fade_out_slider = self.make_slider(0, 100, 10, self.update_fade_out_opacity)
        self.fade_out_label = QLabel("10%")
        popout.add_layout(self.slider_row("Faded opacity", self.fade_out_slider, self.fade_out_label))
        layout.addWidget(popout)

        behaviour = CollapsibleSection("Behaviour", expanded=False)
        self.auto_download_button = QCheckBox("Auto-download new images")
        self.auto_download_button.clicked.connect(self.toggle_auto_download)
        behaviour.add_widget(self.auto_download_button)

        self.media_enabled_button = QCheckBox("Enable GIFs && videos")
        self.media_enabled_button.setToolTip("Show animated GIFs and videos instead of skipping them")
        self.media_enabled_button.clicked.connect(self.toggle_media_options)
        behaviour.add_widget(self.media_enabled_button)

        self.media_autoplay_button = QCheckBox("Autoplay videos as soon as received")
        self.media_autoplay_button.clicked.connect(self.toggle_media_options)
        behaviour.add_widget(self.media_autoplay_button)

        self.media_mute_button = QCheckBox("Mute videos")
        self.media_mute_button.clicked.connect(self.toggle_media_options)
        behaviour.add_widget(self.media_mute_button)

        self.media_volume_slider = self.make_slider(0, 100, 50, self.update_media_volume)
        self.media_volume_label = QLabel("50")
        behaviour.add_layout(self.slider_row("Video volume", self.media_volume_slider, self.media_volume_label))

        self.polling_delay_slider = self.make_slider(10, 60, 10, self.update_polling_delay)
        self.polling_delay_label = QLabel("10s")
        self.polling_delay_widget = QWidget()
        polling_layout = self.slider_row("Poll delay", self.polling_delay_slider, self.polling_delay_label)
        polling_layout.setContentsMargins(0, 0, 0, 0)
        self.polling_delay_widget.setLayout(polling_layout)
        behaviour.add_widget(self.polling_delay_widget)

        self.notif_vol_slider = self.make_slider(0, 100, 30, self.update_notif_vol_timer)
        self.notif_vol_label = QLabel("30")
        behaviour.add_layout(self.slider_row("Notif. volume", self.notif_vol_slider, self.notif_vol_label))
        layout.addWidget(behaviour)

        appearance = CollapsibleSection("Appearance", expanded=False)
        self.theme_combo = NoScrollComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        appearance.add_widget(self.field_label("Theme"))
        appearance.add_widget(self.theme_combo)
        layout.addWidget(appearance)

        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(body)

        dock = QDockWidget("Properties", self)
        dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        dock.setWidget(scroll)
        dock.setMinimumWidth(300)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock)
        self.resizeDocks([dock], [340], QtCore.Qt.Horizontal)

    def build_status_bar(self):
        self.status_label = QLabel("Idle")
        self.statusBar().addWidget(self.status_label)
        self.statusBar().setSizeGripEnabled(False)

    def build_tray(self, images_folder):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(f'{images_folder}/WTPopOutIcon.png'))
        self.tray_icon.show()

        self.tray_menu = QMenu(self)
        self.tray_menu.addAction(QAction('Show', self, triggered=self.show))
        self.tray_menu.addAction(QAction('Exit', self, triggered=self.exit))
        self.tray_icon.setContextMenu(self.tray_menu)

    @staticmethod
    def field_label(text):
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    @staticmethod
    def make_slider(minimum, maximum, value, slot):
        slider = NoScrollSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value)
        slider.valueChanged.connect(slot)
        return slider

    @staticmethod
    def slider_row(title, slider, value_label):
        value_label.setObjectName("value")
        wrapper = QVBoxLayout()
        wrapper.setSpacing(2)
        header = QHBoxLayout()
        header.addWidget(WalltakerApp.field_label(title))
        header.addStretch(1)
        header.addWidget(value_label)
        wrapper.addLayout(header)
        wrapper.addWidget(slider)
        return wrapper

    def apply_theme(self, name):
        if name not in THEMES:
            return
        self.theme_name = name
        self.link_color = THEMES[name]["link"]
        QtWidgets.QApplication.instance().setStyleSheet(build_stylesheet(THEMES[name]))
        if self.theme_combo.currentText() != name:
            self.theme_combo.setCurrentText(name)
        self.fit_play_button()

    def set_play_button(self, playing):
        self.play_action.setText("Pause" if playing else "Play")
        self.play_action.setIcon(self.pause_icon if playing else self.play_icon)

    def fit_play_button(self):
        t = THEMES[self.theme_name]
        self.play_icon = transport_icon("play", t["text"], t["muted"])
        self.pause_icon = transport_icon("pause", t["text"], t["muted"])
        button = self.toolbar.widgetForAction(self.play_action)
        if button is None:
            return
        button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        button.setIconSize(QtCore.QSize(11, 11))
        # The toolbar doesn't regrow a button when its text changes, so reserve room for the longer label
        playing = self.play_action.text() == "Pause"
        widest = 0
        for state in (False, True):
            self.set_play_button(state)
            widest = max(widest, button.sizeHint().width())
        self.set_play_button(playing)
        button.setFixedWidth(widest)

    def show_toast(self, message, success=True):
        self.toast_signal.emit(message, success)

    def _show_toast(self, message, success):
        t = THEMES[self.theme_name]
        self.toast_label.setStyleSheet(f"background: {t['ok'] if success else t['error']};")
        self.toast_label.setText(message)
        self.toast_label.setFixedWidth(min(420, max(160, self.image_label.width() - 24)))
        self.toast_label.adjustSize()
        self.position_toast()
        self.toast_label.show()
        self.toast_label.raise_()
        QTimer.singleShot(3000, self.toast_label.hide)

    def position_toast(self):
        self.toast_label.move(
            (self.image_label.width() - self.toast_label.width()) // 2,
            self.image_label.height() - self.toast_label.height() - 16,
        )

    def set_status(self, text):
        self.status_label.setText(text)

    def update_fade_out_opacity(self, value):
        self.fade_out_num = self.fade_out_slider.value()
        self.fade_out_label.setText(f"{self.fade_out_num}%")
        self.save_settings()
        if self.fade_out_button.isChecked():
            self.popout_window.setWindowOpacity(value / 100)

    def reset_popout_opacity(self):
        if self.popout_window.isVisible():
            self.popout_window.setWindowOpacity(1.0)

    def toggle_fade_out(self):
        self.fade_out_enabled = self.fade_out_button.isChecked()
        if self.fade_out_enabled:
            self.fade_out_timer.start(10000)
        else:
            self.fade_out_timer.stop()
            self.reset_popout_opacity()

    def fade_out_popout(self):
        if self.popout_window.isVisible():
            self.popout_window.setWindowOpacity(self.fade_out_num / 100)

    def toggle_auto_download(self):
        self.auto_download_images = self.auto_download_button.isChecked()
        self.save_settings()

    def toggle_media_options(self, *_):
        self.apply_media_options()
        self.save_settings()

    def apply_media_options(self):
        self.media_enabled = self.media_enabled_button.isChecked()
        self.media_autoplay_button.setEnabled(self.media_enabled)
        self.media_mute_button.setEnabled(self.media_enabled)
        self.media_volume_slider.setEnabled(self.media_enabled)
        self.player.set_muted(self.media_mute_button.isChecked())
        self.player.set_volume(self.media_volume_slider.value())

    def update_media_volume(self, value):
        self.media_volume_label.setText(str(value))
        self.player.set_volume(value)
        self.save_settings()

    def on_playback_state(self, state):
        playing = state == "playing"
        self.set_play_button(playing)
        if state == "playing":
            self.playback_indicator.show_mode("playing", flash_ms=800)
        elif state == "paused":
            self.playback_indicator.show_mode("paused")
        elif state == "ended":
            self.playback_indicator.show_mode("ended")
        else:
            self.playback_indicator.hide()
        self.position_indicator()

    def position_indicator(self):
        size = self.playback_indicator.size()
        self.playback_indicator.move((self.image_label.width() - size.width()) // 2,
                                     (self.image_label.height() - size.height()) // 2)

    def stop_media(self, *_):
        if self.movie is not None:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        self.player.stop()
        self.play_action.setEnabled(False)
        if self.media_path:
            self.media_cache.discard(self.media_path)
            self.media_path = None

    def show_media(self, kind, path):
        self.stop_media()
        if not self.media_enabled:
            self.media_cache.discard(path)
            return
        self.media_path = path
        self.current_pixmap = None
        if kind == "gif":
            with open(path, "rb") as f:
                data = QtCore.QByteArray(f.read())
            buffer = QtCore.QBuffer(self)
            buffer.setData(data)
            buffer.open(QtCore.QIODevice.ReadOnly)
            self.movie = QMovie(buffer, QtCore.QByteArray(), self)
            buffer.setParent(self.movie)
            self.movie.setCacheMode(QMovie.CacheNone)
            self.movie.frameChanged.connect(self.on_gif_frame)
            self.movie.finished.connect(self.movie.start)
            self.movie.start()
        else:
            self.player.load(path, self.media_autoplay_button.isChecked(), self.media_mute_button.isChecked())
            self.play_action.setEnabled(True)
        self.announce_new_media()

    def on_gif_frame(self, *_):
        if self.movie is not None:
            self.show_frame(self.movie.currentPixmap())

    def on_video_frame(self, image):
        if self.player.is_active:
            self.show_frame(QPixmap.fromImage(image))

    def on_player_error(self, message):
        self.show_toast(message, success=False)

    def show_frame(self, pixmap):
        if pixmap.isNull():
            return
        self.current_pixmap = pixmap
        self.render_viewport_pixmap()
        if self.popout_window.isVisible():
            self.popout_window.update_image(pixmap)

    def toggle_video_playback(self):
        if not self.player.is_active:
            return
        if self.player.is_playing:
            self.player.pause()
        else:
            self.player.play()

    def announce_new_media(self):
        self.set_status(f"Showing media from {self.username}" if self.username else "Media loaded")
        self.play_notification_sound()
        self.reset_popout_opacity()
        self.toggle_fade_out()

    def current_service(self):
        return get_service(
            self.service_combo.currentData(),
            self.custom_host.text(),
            bool(self.custom_mode_combo.currentData()),
        )

    def on_service_changed(self, *_):
        self.custom_widgets.setVisible(self.service_combo.currentData() == CUSTOM_SERVICE)
        self.update_polling_visibility()
        self.save_settings()

    def update_polling_visibility(self, *_):
        key = self.service_combo.currentData()
        if key == CUSTOM_SERVICE:
            realtime = bool(self.custom_mode_combo.currentData())
        else:
            realtime = get_service(key).realtime
        self.polling_delay_widget.setVisible(not realtime)

    def fetch_media(self, url, backup_url=None):
        headers = {"User-Agent": CLIENT_NAME}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200 and backup_url:
            response = requests.get(backup_url, headers=headers, timeout=30)
        return response

    def deliver_media(self, url, backup_url):
        """Fetches the post on a worker thread and hands it to the UI thread. Returns False if skipped."""
        kind = media_kind(url)
        if kind == "image":
            response = self.fetch_media(url, backup_url)
            response.raise_for_status()
            pixmap = decode_pixmap(response.content)
            del response
            self.image_signal.emit(pixmap)
            return True
        if not self.media_enabled:
            self.show_toast(UNSUPPORTED_MESSAGE, success=False)
            return False
        path = self.media_cache.download(url, backup_url, {"User-Agent": CLIENT_NAME})
        self.media_signal.emit(kind, path)
        return True

    def download_image(self):
        if self.image_link:
            response = self.fetch_media(self.image_link, self.image_backup_link)
            if response.status_code == 200:
                downloads_folder = 'downloads'
                if not os.path.exists(downloads_folder):
                    os.makedirs(downloads_folder)

                extension = '.png'
                if media_kind(self.image_link) != "image":
                    extension = os.path.splitext(urlparse(self.image_link).path)[1].lower()
                existing_images = [f for f in os.listdir(downloads_folder) if f.startswith('img_')]
                image_number = len(existing_images) + 1

                timestamp = datetime.datetime.now().strftime('%Y-%m-%d')
                image_path = os.path.join(downloads_folder, f'img_{image_number} {timestamp}{extension}')

                with open(image_path, 'wb') as f:
                    f.write(response.content)
                self.show_toast("Image downloaded!", success=True)
            else:
                self.show_toast("Download Failed!", success=False)
        else:
            self.show_toast("No image link!", success=False)

    def show_sent_response(self, response_type, text):
        emoji = {"horny": "😍", "came": "💦", "disgust": "🤮", "ok": "👍"}.get(response_type)
        if not response_type and not text:
            self.sent_response_label.hide()
            return
        self.sent_response_label.setText(f"Sent: {emoji or ''} {text or ''}".replace("  ", " ").strip())
        self.sent_response_label.show()

    def on_came_clicked(self):
        if not self.username:
            self.show_toast("No setter to send this to yet!", success=False)
            return
        dialog = CameDialog(self, self.username, self.windowIcon())
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.send_custom_response("💦", dialog.message())

    def on_send_clicked(self):
        self.send_custom_response(self.response_type_combo.currentText(), self.custom_response_entry.text())

    def send_custom_response(self, response_type, custom_response):
        response_type_map = {
            "😍": "horny",
            "💦": "came",
            "🤮": "disgust",
            "👍": "ok",
        }
        actual_response_type = response_type_map.get(response_type, "ok")

        if not self.link_id.text() or not self.api_key.text():
            self.show_toast("Link ID and API key are required!", success=False)
            return False

        service = self.current_service()
        link_id = self.link_id.text()
        if service.realtime:
            link_id = self.numeric_link_id or link_id

        url = f"{service.base_url}/api/links/{link_id}/response.json"
        payload = {
            "api_key": self.api_key.text(),
            "type": actual_response_type,
            "text": custom_response if custom_response else response_type,
        }
        headers = {"User-Agent": CLIENT_NAME if service.realtime else "WTPopOutViewer"}

        try:
            if service.realtime:
                response = requests.post(url, json=payload, headers=headers, timeout=30)
            else:
                response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()

            self.show_toast("Response sent!", success=True)
            self.response_signal.emit(actual_response_type, payload["text"])
            self.custom_response_entry.clear()
            return True
        except requests.exceptions.RequestException as req_err:
            self.show_toast(f"Request error: {req_err}", success=False)
        except Exception as e:
            self.show_toast(f"Unexpected error: {e}", success=False)
        return False

    def save_settings(self, *_):
        self.save_timer.start(400)

    def flush_settings(self):
        if self.save_timer.isActive():
            self.save_timer.stop()
            self.write_settings()

    def write_settings(self):
        self.settings_manager.save_settings(
            self.link_id.text(),
            self.api_key.text(),
            self.polling_delay_slider.value(),
            self.popout_size_slider.value(),
            self.notif_vol_slider.value(),
            self.auto_download_button.isChecked(),
            self.fade_out_button.isChecked(),
            self.fade_out_slider.value(),
            self.service_combo.currentData(),
            self.custom_host.text().strip(),
            bool(self.custom_mode_combo.currentData()),
            self.media_enabled_button.isChecked(),
            self.media_autoplay_button.isChecked(),
            self.media_mute_button.isChecked(),
            self.media_volume_slider.value(),
        )

    def fetch_user_info(self, username):
        api_key = self.api_key.text()
        if not api_key:
            self.show_toast("An API key is required!", success=False)
            return

        url = f"{self.current_service().base_url}/api/users/{username}.json?api_key={api_key}"
        headers = {"User-Agent": "WTPopOutViewer"}
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            user_data = response.json()
            self.username = user_data['username']
            self.user_account_link = f"{self.current_service().base_url}/users/{self.username}"
            self.user_info_signal.emit(user_data)
        except Exception as e:
            self.show_toast("Error fetching user info: " + str(e), success=False)

    def display_user_info(self, user_data):
        for i in reversed(range(self.user_info_layout.count())):
            widget = self.user_info_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        def add(text, link=False):
            label = QLabel(text)
            label.setWordWrap(True)
            if link:
                label.setOpenExternalLinks(True)
            self.user_info_layout.addWidget(label)

        style = f"color: {self.link_color};"
        add(f"Set by <a href='{self.user_account_link}' style='{style}'>{self.username}</a>, "
            f"they've set {user_data['set_count']} link(s)", link=True)
        add(f"{user_data['username']} {'is' if user_data['online'] else 'is not'} online")

        if 'friend' in user_data:
            add(f"{user_data['username']} {'is your' if user_data['friend'] else 'is not your'} friend!")
        else:
            add("Your API key was incorrect! Please restart and input a correct API key for this to work.")

        if self.image_link:
            add(f"<a href='{self.image_link}' style='{style}'>Image link</a>", link=True)

    def start_polling(self):
        if not self.link_id.text() or not self.api_key.text():
            self.show_toast("Please enter both Link ID and API key!", success=False)
            return

        service = self.current_service()
        if self.service_combo.currentData() == CUSTOM_SERVICE and service.key != CUSTOM_SERVICE:
            self.show_toast("Enter a host for the custom service!", success=False)
            return
        if service.realtime and websocket is None:
            self.show_toast("The 'websocket-client' package is required for this service (pip install websocket-client).", success=False)
            return

        self.username = None
        self.numeric_link_id = None
        self.save_settings()
        self.start_action.setEnabled(False)
        self.is_polling = True
        self.link_id.setEnabled(False)
        self.api_key.setEnabled(False)
        self.service_combo.setEnabled(False)
        self.custom_widgets.setEnabled(False)

        if service.realtime:
            self.start_action.setText("●  Live")
            self.set_status(f"Connecting to link {self.link_id.text()}")
            threading.Thread(
                target=self.stream_data,
                args=(service, self.link_id.text().strip(), self.api_key.text()),
                daemon=True,
            ).start()
        else:
            self.start_action.setText("●  Polling")
            self.set_status(f"Polling link {self.link_id.text()}")
            threading.Thread(target=self.poll_data, daemon=True).start()

    def poll_data(self):
        last_post_url = None
        while self.is_polling:
            url = f"{self.current_service().base_url}/links/{self.link_id.text()}.json"
            headers = {"User-Agent": "WTPopOutViewer"}
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if data['post_url'] != last_post_url:
                    self.image_link = data["post_url"]
                    self.image_backup_link = data.get("post_url_backup")
                    last_post_url = self.image_link
                    self.fetch_user_info(data['set_by'])
                    if self.deliver_media(self.image_link, self.image_backup_link) and self.auto_download_button.isChecked():
                        self.download_image()

            except Exception as e:
                self.show_toast(f"Polling failed: {e}", success=False)

            time.sleep(self.polling_interval)

    def stream_data(self, service, link_id, api_key):
        identifier = json.dumps({
            "channel": "LinkChannel",
            "link_id": int(link_id) if link_id.isdigit() else link_id,
            "client": CLIENT_NAME,
        })
        state = {"last_post_url": None, "last_error": None}

        def send_command(ws, command, data=None):
            frame = {"command": command, "identifier": identifier}
            if data is not None:
                frame["data"] = json.dumps(data)
            ws.send(json.dumps(frame))

        def on_open(ws):
            send_command(ws, "subscribe")
            self.status_signal.emit(f"Connected, waiting for link {link_id}")

        def on_message(ws, raw):
            try:
                envelope = json.loads(raw)
                kind = envelope.get("type")
                if kind == "reject_subscription":
                    self.show_toast("Lycraon rejected the subscription.", success=False)
                    return
                if kind == "disconnect":
                    ws.close()
                    return
                message = envelope.get("message")
                if not isinstance(message, dict):
                    return
                if message.get("type") == "user":
                    self.handle_stream_user(service, message)
                else:
                    self.handle_stream_link(ws, message, state, send_command, api_key)
            except Exception as e:
                self.show_toast(f"Stream error: {e}", success=False)

        def on_error(ws, error):
            self.show_toast(f"Connection error: {error}", success=False)

        while self.is_polling:
            self.ws = websocket.WebSocketApp(
                service.cable_url,
                header=[f"User-Agent: {CLIENT_NAME}"],
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
            )
            self.ws.run_forever(ping_interval=30, ping_timeout=10)

            self.status_signal.emit("Disconnected, reconnecting…")
            for _ in range(50):
                if not self.is_polling:
                    return
                time.sleep(0.1)

    def handle_stream_link(self, ws, link, state, send_command, api_key):
        if not link.get("success", True):
            why = link.get("why", "Unknown error")
            if why != state["last_error"]:
                state["last_error"] = why
                self.show_toast(why, success=False)
            return
        state["last_error"] = None

        self.numeric_link_id = link.get("id", self.numeric_link_id)
        self.response_signal.emit(link.get("response_type"), link.get("response_text"))
        post_url = link.get("post_url")
        if not post_url or post_url == state["last_post_url"]:
            return

        self.image_link = post_url
        self.image_backup_link = link.get("post_url_backup")

        set_by = link.get("set_by")
        if set_by:
            send_command(ws, "message", {"action": "watch_user", "username": set_by, "api_key": api_key})

        delivered = self.deliver_media(post_url, self.image_backup_link)
        state["last_post_url"] = post_url
        if delivered and self.auto_download_button.isChecked():
            self.download_image()

    def handle_stream_user(self, service, message):
        user = message.get("user")
        if not message.get("success") or not isinstance(user, dict):
            return
        self.username = user.get("username")
        self.user_account_link = f"{service.base_url}/users/{self.username}"
        self.user_info_signal.emit({
            "username": self.username,
            "set_count": user.get("set_count", 0),
            "online": user.get("online", False),
            **({"friend": user["friend"]} if "friend" in user else {}),
        })

    def update_image_label(self, pixmap):
        self.image_label.clear()
        self.current_pixmap = None
        self.current_pixmap = pixmap
        self.render_viewport_pixmap()
        gc.collect()
        self.set_status(f"Showing image from {self.username}" if self.username else "Image loaded")
        self.play_notification_sound()

    def play_notification_sound(self):
        current_dir = pathlib.Path(__file__).parent
        try:
            if not self.audio_ready:
                pygame.mixer.init()
                pygame.mixer.music.load(str(current_dir / 'sounds' / 'notif.mp3'))
                self.audio_ready = True
            pygame.mixer.music.set_volume(self.notif_vol_slider.value() / 100)
            pygame.mixer.music.play()
        except pygame.error as e:
            self.show_toast(f"Notification sound unavailable: {e}", success=False)

    def render_viewport_pixmap(self, smooth=True):
        if self.current_pixmap is None:
            return
        size = self.image_label.size() - QtCore.QSize(8, 8)
        mode = QtCore.Qt.SmoothTransformation if smooth else QtCore.Qt.FastTransformation
        self.image_label.setPixmap(self.current_pixmap.scaled(size, QtCore.Qt.KeepAspectRatio, mode))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layout_edge_grips()
        self.render_viewport_pixmap(smooth=False)
        self.smooth_render_timer.start(150)
        if self.toast_label.isVisible():
            self.position_toast()
        self.position_indicator()

    def toggle_popout_mode(self, enabled):
        self.popout_toggle_button.setChecked(enabled)
        self.popout_action.setChecked(enabled)
        if enabled:
            self.popout_toggle_button.setText("Disable Pop-Out Mode")
            self.popout_window.show()
            if self.current_pixmap is not None:
                self.popout_window.update_image(self.current_pixmap)
        else:
            self.popout_toggle_button.setText("Enable Pop-Out Mode")
            self.popout_window.hide()
        self.save_settings()

    def update_popout_size(self, value):
        self.popout_size_label.setText(f"{value}px")
        self.popout_size_timer.stop()
        self.popout_size_timer.start(self.popout_delay)
        self.save_settings()

    def update_popout_size_timer(self):
        self.popout_window.max_width = self.popout_size_slider.value()
        self.popout_window.max_height = self.popout_size_slider.value()
        if self.popout_window.isVisible() and self.current_pixmap is not None:
            self.popout_window.update_image(self.current_pixmap)

    def update_polling_delay(self, value):
        self.polling_delay_label.setText(f"{value}s")
        self.polling_delay_timer.stop()
        self.polling_delay_timer.start(self.polling_delay)
        self.save_settings()

    def update_polling_delay_timer(self):
        self.polling_interval = self.polling_delay_slider.value()

    def update_notif_vol_timer(self, *_):
        self.notif_vol_label.setText(f"{self.notif_vol_slider.value()}")
        self.save_settings()

    def load_settings(self):
        settings = self.settings_manager.load_settings()
        service_index = self.service_combo.findData(settings["service"])
        self.service_combo.blockSignals(True)
        self.service_combo.setCurrentIndex(service_index if service_index >= 0 else self.service_combo.findData(DEFAULT_SERVICE))
        self.service_combo.blockSignals(False)
        self.custom_host.setText(settings["custom_host"])
        self.custom_mode_combo.blockSignals(True)
        self.custom_mode_combo.setCurrentIndex(self.custom_mode_combo.findData(bool(settings["custom_realtime"])))
        self.custom_mode_combo.blockSignals(False)
        self.custom_widgets.setVisible(self.service_combo.currentData() == CUSTOM_SERVICE)
        self.update_polling_visibility()
        self.link_id.setText(settings["link_id"])
        self.api_key.setText(settings["api_key"])
        self.polling_delay_slider.setValue(settings["polling_delay"])
        self.popout_size_slider.setValue(settings["popout_size"])
        self.notif_vol_slider.setValue(settings["notif_vol"])
        self.auto_download_button.setChecked(settings["auto_download"])
        self.media_enabled_button.setChecked(settings["media_enabled"])
        self.media_autoplay_button.setChecked(settings["media_autoplay"])
        self.media_mute_button.setChecked(settings["media_mute"])
        self.media_volume_slider.setValue(settings["media_volume"])
        self.media_volume_label.setText(str(self.media_volume_slider.value()))
        self.apply_media_options()
        self.fade_out_button.setChecked(settings["fade_out"])
        self.fade_out_slider.setValue(settings["fade_out_number"])
        self.popout_size_label.setText(f"{self.popout_size_slider.value()}px")
        self.polling_delay_label.setText(f"{self.polling_delay_slider.value()}s")
        self.notif_vol_label.setText(f"{self.notif_vol_slider.value()}")
        self.fade_out_label.setText(f"{self.fade_out_slider.value()}%")
        self.polling_interval = self.polling_delay_slider.value()
        self.fade_out_num = self.fade_out_slider.value()
        self.popout_window.max_width = self.popout_size_slider.value()
        self.popout_window.max_height = self.popout_size_slider.value()

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.WindowStateChange:
            self.title_bar.sync_state()
            self.layout_edge_grips()
        super().changeEvent(event)

    def layout_edge_grips(self):
        m = EdgeGrip.SIZE
        w, h = self.width(), self.height()
        rects = {
            "left": (0, m, m, h - 2 * m), "right": (w - m, m, m, h - 2 * m),
            "top": (m, 0, w - 2 * m, m), "bottom": (m, h - m, w - 2 * m, m),
            "topleft": (0, 0, m, m), "topright": (w - m, 0, m, m),
            "bottomleft": (0, h - m, m, m), "bottomright": (w - m, h - m, m, m),
        }
        maximized = self.isMaximized()
        for name, grip in self.edge_grips.items():
            grip.setGeometry(*rects[name])
            grip.setVisible(not maximized)
            grip.raise_()

    def closeEvent(self, event):
        if self.is_polling:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage('Walltaker', 'Running in background')
        else:
            self.flush_settings()
            event.accept()

    def exit(self):
        self.is_polling = False
        self.flush_settings()
        if self.ws is not None:
            self.ws.close()
        self.popout_window.close()
        self.stop_media()
        self.media_cache.cleanup()
        self.tray_icon.showMessage('Walltaker', 'Closing...')
        self.close()
