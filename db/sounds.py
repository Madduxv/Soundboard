from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".mov"}


@dataclass(frozen=True)
class Sound:
    id: int
    filename: str
    display_name: str
    sort_order: int


class SoundStore:
    def __init__(self, db_path: Path, sounds_dir: Path) -> None:
        self.db_path = db_path
        self.sounds_dir = sounds_dir
        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

    def sync_directory(self) -> list[Sound]:
        files_on_disk = {
            path.name
            for path in self.sounds_dir.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        }

        with self._connect() as connection:
            rows = connection.execute("SELECT id, filename FROM sounds").fetchall()
            known = {row["filename"]: row["id"] for row in rows}

            for filename in sorted(files_on_disk - known.keys()):
                display_name = self._default_display_name(filename)
                sort_order = self._next_sort_order(connection)
                connection.execute(
                    """
                    INSERT INTO sounds (filename, display_name, sort_order, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (filename, display_name, sort_order, datetime.now(UTC).isoformat()),
                )

            for filename, sound_id in known.items():
                if filename not in files_on_disk:
                    connection.execute("DELETE FROM sounds WHERE id = ?", (sound_id,))

        return self.list_sounds()

    def list_sounds(self) -> list[Sound]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, filename, display_name, sort_order
                FROM sounds
                ORDER BY sort_order, id
                """
            ).fetchall()
        return [
            Sound(
                id=row["id"],
                filename=row["filename"],
                display_name=row["display_name"],
                sort_order=row["sort_order"],
            )
            for row in rows
        ]

    def get_by_id(self, sound_id: int) -> Sound | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, filename, display_name, sort_order
                FROM sounds
                WHERE id = ?
                """,
                (sound_id,),
            ).fetchone()
        if row is None:
            return None
        return Sound(
            id=row["id"],
            filename=row["filename"],
            display_name=row["display_name"],
            sort_order=row["sort_order"],
        )

    def get_path(self, sound_id: int) -> Path | None:
        sound = self.get_by_id(sound_id)
        if sound is None:
            return None
        path = self.sounds_dir / sound.filename
        return path if path.is_file() else None

    def update_display_name(self, sound_id: int, display_name: str) -> Sound | None:
        cleaned = display_name.strip()
        if not cleaned:
            raise ValueError("display name cannot be empty")

        with self._connect() as connection:
            connection.execute(
                "UPDATE sounds SET display_name = ? WHERE id = ?",
                (cleaned, sound_id),
            )
        return self.get_by_id(sound_id)

    def delete_sound(self, sound_id: int) -> bool:
        sound = self.get_by_id(sound_id)
        if sound is None:
            return False

        path = self.sounds_dir / sound.filename
        if path.is_file():
            path.unlink()

        with self._connect() as connection:
            connection.execute("DELETE FROM sounds WHERE id = ?", (sound_id,))
        return True

    def add_upload(self, filename: str, data: bytes, display_name: str | None = None) -> Sound:
        safe_name = self._safe_filename(filename)
        if safe_name.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError("unsupported audio format")

        target = self._unique_path(safe_name)
        target.write_bytes(data)

        label = (display_name or self._default_display_name(target.name)).strip()
        if not label:
            label = self._default_display_name(target.name)

        with self._connect() as connection:
            sort_order = self._next_sort_order(connection)
            cursor = connection.execute(
                """
                INSERT INTO sounds (filename, display_name, sort_order, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (target.name, label, sort_order, datetime.now(UTC).isoformat()),
            )
            sound_id = cursor.lastrowid

        sound = self.get_by_id(sound_id)
        if sound is None:
            raise RuntimeError("failed to save uploaded sound")
        return sound

    @staticmethod
    def _default_display_name(filename: str) -> str:
        return Path(filename).stem.replace("_", " ")

    @staticmethod
    def _next_sort_order(connection: sqlite3.Connection) -> int:
        row = connection.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM sounds").fetchone()
        return int(row[0])

    def _safe_filename(self, filename: str) -> Path:
        basename = Path(filename).name
        stem = re.sub(r"[^\w\s-]", "", Path(basename).stem).strip().replace(" ", "_")
        suffix = Path(basename).suffix.lower()
        if not stem:
            stem = "sound"
        return Path(f"{stem}{suffix}")

    def _unique_path(self, filename: Path) -> Path:
        target = self.sounds_dir / filename.name
        if not target.exists():
            return target

        stem = filename.stem
        suffix = filename.suffix
        counter = 1
        while True:
            candidate = self.sounds_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
