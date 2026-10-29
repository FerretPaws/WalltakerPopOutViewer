import atexit
import itertools
import os
import shutil
import tempfile
import threading
import time
from urllib.parse import urlparse

import requests
from PyQt5 import QtCore
from PyQt5.QtGui import QImage

try:
    import av
except ImportError:
    av = None

try:
    import pygame
except ImportError:
    pygame = None

MAX_VIDEO_EDGE = 1920
MAX_AUDIO_BYTES = 200 * 1024 * 1024

GIF_EXTENSIONS = ('.gif',)
VIDEO_EXTENSIONS = ('.mp4', '.webm', '.mov', '.m4v')


def media_kind(url):
    path = urlparse(url).path.lower()
    if path.endswith(GIF_EXTENSIONS):
        return "gif"
    if path.endswith(VIDEO_EXTENSIONS):
        return "video"
    return "image"


class MediaCache:
    def __init__(self):
        self.folder = None
        self.pending = []
        self.counter = itertools.count(1)
        atexit.register(self.cleanup)

    def download(self, url, backup_url, headers):
        if self.folder is None:
            self.folder = tempfile.mkdtemp(prefix="WalltakerPopOutViewer_")
        extension = os.path.splitext(urlparse(url).path)[1].lower() or ".bin"
        path = os.path.join(self.folder, f"media_{next(self.counter)}{extension}")

        response = requests.get(url, headers=headers, timeout=30, stream=True)
        if response.status_code != 200 and backup_url:
            response.close()
            response = requests.get(backup_url, headers=headers, timeout=30, stream=True)
        with response:
            response.raise_for_status()
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    f.write(chunk)
        return path

    def discard(self, path):
        if path:
            self.pending.append(path)
        # Files still held open by the media backend are retried on the next call
        self.pending = [p for p in self.pending if not self._remove(p)]

    @staticmethod
    def _remove(path):
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return False

    def cleanup(self):
        if self.folder:
            shutil.rmtree(self.folder, ignore_errors=True)
            self.folder = None
            self.pending = []


class VideoPlayer(QtCore.QObject):
    """Decodes video with PyAV (no dependency on system codecs) and plays its audio through pygame."""

    frame_ready = QtCore.pyqtSignal(QImage)
    error = QtCore.pyqtSignal(str)
    state_changed = QtCore.pyqtSignal(str)  # "playing", "paused", "ended" or "stopped"
    _tick = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tick.connect(self._deliver)
        self._lock = threading.Lock()
        self._latest = None
        self._tick_pending = False
        self._generation = 0
        self._thread = None
        self._path = None
        self._muted = False
        self._volume = 1.0
        self._paused = True
        self._paused_pos = 0.0
        self._base = 0.0
        self._sound = None
        self._channel = None
        self._ended = False

    @property
    def is_playing(self):
        return self._thread is not None and not self._ended and not self._paused

    @property
    def is_active(self):
        return self._path is not None

    def load(self, path, autoplay, muted):
        self.stop()
        if av is None:
            self.error.emit("Video playback needs the 'av' package (pip install av).")
            return
        self._path = path
        self._muted = muted
        self._start(paused=not autoplay)

    def _start(self, paused):
        self._generation += 1
        self._ended = False
        self._paused = paused
        self._paused_pos = 0.0
        self._base = time.monotonic()
        self._thread = threading.Thread(target=self._run, args=(self._generation, self._path), daemon=True)
        self._thread.start()
        self.state_changed.emit("paused" if paused else "playing")

    def play(self):
        if self._path is None:
            return
        if self._ended:
            self._start(paused=False)
        elif self._paused:
            self._base = time.monotonic() - self._paused_pos
            self._paused = False
            if self._channel is not None:
                self._channel.unpause()
            self.state_changed.emit("playing")

    def pause(self):
        if self._path is None or self._paused or self._ended:
            return
        self._paused_pos = self._position()
        self._paused = True
        if self._channel is not None:
            self._channel.pause()
        self.state_changed.emit("paused")

    def set_muted(self, muted):
        self._muted = muted
        self._apply_volume()

    def set_volume(self, percent):
        self._volume = max(0, min(100, percent)) / 100
        self._apply_volume()

    def stop(self):
        was_active = self._path is not None
        self._generation += 1
        thread, self._thread = self._thread, None
        sound, self._sound = self._sound, None
        self._channel = None
        if sound is not None:
            sound.stop()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._path = None
        self._ended = False
        with self._lock:
            self._latest = None
        if was_active:
            self.state_changed.emit("stopped")

    def _position(self):
        return self._paused_pos if self._paused else time.monotonic() - self._base

    def _apply_volume(self):
        if self._channel is not None:
            self._channel.set_volume(0.0 if self._muted else self._volume)

    def _publish(self, image):
        with self._lock:
            self._latest = image
            if self._tick_pending:
                return
            self._tick_pending = True
        self._tick.emit()

    def _deliver(self):
        with self._lock:
            image, self._latest = self._latest, None
            self._tick_pending = False
        if image is not None:
            self.frame_ready.emit(image)

    def _decode_audio(self, path, generation):
        if pygame is None:
            return None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            frequency, _, channels = pygame.mixer.get_init()
            with av.open(path) as container:
                if not container.streams.audio:
                    return None
                layout = "mono" if channels == 1 else "stereo"
                resampler = av.AudioResampler(format="s16", layout=layout, rate=frequency)
                chunks, size = [], 0
                frames = container.decode(audio=0)
                pending = True
                while pending and generation == self._generation:
                    try:
                        frame = next(frames)
                        out_frames = resampler.resample(frame)
                    except StopIteration:
                        out_frames = resampler.resample(None)
                        pending = False
                    for out in out_frames:
                        data = bytes(out.planes[0])[:out.samples * channels * 2]
                        chunks.append(data)
                        size += len(data)
                    if size > MAX_AUDIO_BYTES:
                        break
            if generation != self._generation or not chunks:
                return None
            return pygame.mixer.Sound(buffer=b"".join(chunks))
        except Exception:
            return None

    def _to_image(self, frame, scale):
        if scale is not None:
            frame = frame.reformat(width=scale[0], height=scale[1], format="rgb24")
        else:
            frame = frame.reformat(format="rgb24")
        plane = frame.planes[0]
        return QImage(bytes(plane), frame.width, frame.height, plane.line_size, QImage.Format_RGB888).copy()

    def _run(self, generation, path):
        try:
            with av.open(path) as container:
                if not container.streams.video:
                    raise ValueError("No video stream found")
                stream = container.streams.video[0]
                stream.thread_type = "AUTO"
                scale = None
                longest = max(stream.codec_context.width, stream.codec_context.height)
                if longest > MAX_VIDEO_EDGE:
                    ratio = MAX_VIDEO_EDGE / longest
                    scale = (max(2, int(stream.codec_context.width * ratio) // 2 * 2),
                             max(2, int(stream.codec_context.height * ratio) // 2 * 2))

                first_time = None
                started = False
                for frame in container.decode(stream):
                    if generation != self._generation:
                        return
                    frame_time = frame.time if frame.time is not None else 0.0
                    if first_time is None:
                        first_time = frame_time
                    frame_time -= first_time

                    if not started:
                        self._publish(self._to_image(frame, scale))
                        started = True
                        sound = self._decode_audio(path, generation)
                        if generation != self._generation:
                            return
                        if sound is not None:
                            self._sound = sound
                            self._channel = sound.play()
                            self._apply_volume()
                            if self._paused and self._channel is not None:
                                self._channel.pause()
                        if not self._paused:
                            self._base = time.monotonic()
                        continue

                    while generation == self._generation and (self._paused or self._position() < frame_time):
                        time.sleep(0.004)
                    if generation != self._generation:
                        return
                    if self._position() - frame_time < 0.15:
                        self._publish(self._to_image(frame, scale))
            if generation == self._generation:
                self._ended = True
                self.state_changed.emit("ended")
        except Exception as e:
            if generation == self._generation:
                self._ended = True
                self.state_changed.emit("ended")
                self.error.emit(f"Video playback failed: {e}")
