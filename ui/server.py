from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from audio.player import AudioPlayer
from db.sounds import SoundStore
from ui.upload import parse_multipart

UI_DIR = Path(__file__).resolve().parent
PROJECT_DIR = UI_DIR.parent
SOUNDS_DIR = PROJECT_DIR / "sounds"
DB_PATH = PROJECT_DIR / "soundboard.db"

player = AudioPlayer()
store = SoundStore(DB_PATH, SOUNDS_DIR)


class SoundboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._serve_file(UI_DIR / "index.html", "text/html")
        elif parsed.path == "/app.js":
            self._serve_file(UI_DIR / "app.js", "application/javascript")
        elif parsed.path == "/api/sounds":
            sounds = [
                {
                    "id": sound.id,
                    "name": sound.display_name,
                    "file": sound.filename,
                }
                for sound in store.list_sounds()
            ]
            self._json_response(sounds)
        elif parsed.path == "/api/devices":
            devices = player.list_output_devices()
            self._json_response({"devices": devices})
        elif parsed.path == "/api/config":
            from ui.config import load_config

            self._json_response(load_config())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/sounds/upload":
            self._handle_upload()
        elif parsed.path == "/api/sounds/sync":
            sounds = store.sync_directory()
            self._json_response(
                [
                    {"id": sound.id, "name": sound.display_name, "file": sound.filename}
                    for sound in sounds
                ]
            )
        elif parsed.path == "/api/sounds/update":
            body = self._read_json_body()
            sound_id = body.get("id")
            display_name = body.get("name")
            if not sound_id or display_name is None:
                self._json_response({"error": "missing id or name"}, status=400)
                return
            try:
                sound = store.update_display_name(int(sound_id), str(display_name))
            except ValueError as error:
                self._json_response({"error": str(error)}, status=400)
                return
            if sound is None:
                self._json_response({"error": "not found"}, status=404)
                return
            self._json_response(
                {"id": sound.id, "name": sound.display_name, "file": sound.filename}
            )
        elif parsed.path == "/api/sounds/delete":
            body = self._read_json_body()
            sound_id = body.get("id")
            if sound_id is None:
                self._json_response({"error": "missing id"}, status=400)
                return
            if not store.delete_sound(int(sound_id)):
                self._json_response({"error": "not found"}, status=404)
                return
            self._json_response({"ok": True})
        elif parsed.path == "/api/play":
            body = self._read_json_body()
            sound_id = body.get("id")
            if sound_id is None:
                self._json_response({"error": "missing id"}, status=400)
                return
            path = store.get_path(int(sound_id))
            if path is None:
                self._json_response({"error": "not found"}, status=404)
                return
            player.play(path)
            self._json_response({"ok": True})
        elif parsed.path == "/api/stop":
            player.stop_all()
            self._json_response({"ok": True})
        elif parsed.path == "/api/config":
            from ui.config import load_config, save_config

            body = self._read_json_body()
            config = load_config()
            if "device" in body:
                device = body["device"] or None
                player.set_device(device)
                config["device"] = device or ""
            if "volume" in body:
                volume = float(body["volume"])
                player.set_volume(volume)
                config["volume"] = volume
            save_config(config)
            self._json_response(config)
        else:
            self.send_error(404)

    def _handle_upload(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._json_response({"error": "expected multipart upload"}, status=400)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            form = parse_multipart(body, content_type)
        except ValueError as error:
            self._json_response({"error": str(error)}, status=400)
            return

        upload = form.files.get("file")
        if upload is None or not upload.data:
            self._json_response({"error": "missing file"}, status=400)
            return

        display_name = form.fields.get("name") or None
        try:
            sound = store.add_upload(upload.filename, upload.data, display_name)
        except ValueError as error:
            self._json_response({"error": str(error)}, status=400)
            return

        self._json_response(
            {"id": sound.id, "name": sound.display_name, "file": sound.filename},
            status=201,
        )

    def _serve_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def _json_response(self, data: object, status: int = 200) -> None:
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    from ui.config import load_config, preferred_device

    store.sync_directory()

    config = load_config()
    devices = player.list_output_devices()
    device = preferred_device(devices, config.get("device"))
    if device:
        player.set_device(device)
    player.set_volume(config.get("volume", 1.0))

    server = ThreadingHTTPServer((host, port), SoundboardHandler)
    url = f"http://{host}:{port}"

    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()

    print(f"Soundboard running at {url}")
    print("Press Ctrl+C to quit.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        player.stop_all()
        server.shutdown()
