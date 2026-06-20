from __future__ import annotations

import threading
from pathlib import Path

import miniaudio
import numpy as np
import sounddevice as sd


class AudioPlayer:
    SOUNDS_DIR = Path(__file__).resolve().parent.parent / "sounds"
    AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".mov"}

    def __init__(self) -> None:
        self._audio_lock = threading.Lock()
        self._volume = 1.0
        self._device_name: str | None = None
        self._cache: dict[str, tuple[np.ndarray, int]] = {}

    @staticmethod
    def _clean_device_name(name: str) -> str:
        return name.split(",")[0].strip()

    @staticmethod
    def list_output_devices() -> list[str]:
        devices: list[str] = []
        for device in sd.query_devices():
            if device["max_output_channels"] > 0:
                devices.append(AudioPlayer._clean_device_name(device["name"]))
        return devices

    def set_device(self, device_name: str | None) -> None:
        self._device_name = device_name or None

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))

    def list_sounds(self) -> list[Path]:
        if not self.SOUNDS_DIR.is_dir():
            return []
        return sorted(
            path
            for path in self.SOUNDS_DIR.iterdir()
            if path.suffix.lower() in self.AUDIO_EXTENSIONS and path.is_file()
        )

    def play(self, path: Path) -> None:
        thread = threading.Thread(target=self._play_file, args=(path,), daemon=True)
        thread.start()

    def stop_all(self) -> None:
        with self._audio_lock:
            sd.stop()

    def _resolve_device_index(self) -> int | None:
        if not self._device_name:
            return None
        for index, device in enumerate(sd.query_devices()):
            if device["max_output_channels"] > 0 and self._device_name in device["name"]:
                return index
        return None

    def _load_samples(self, path: Path) -> tuple[np.ndarray, int]:
        key = str(path.resolve())
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        decoded = miniaudio.decode_file(str(path))
        samples = np.frombuffer(decoded.samples.tobytes(), dtype=np.int16).reshape(
            -1, decoded.nchannels
        )
        cached = (samples, decoded.sample_rate)
        self._cache[key] = cached
        return cached

    def _play_file(self, path: Path) -> None:
        samples, sample_rate = self._load_samples(path)
        volume = self._volume
        if volume < 1.0:
            samples = (samples.astype(np.float32) * volume).astype(np.int16)
        else:
            samples = samples.copy()

        device = self._resolve_device_index()
        with self._audio_lock:
            sd.play(samples, sample_rate, device=device)
