from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def preferred_device(devices: list[str], saved: str | None) -> str | None:
    if saved and saved in devices:
        return saved
    for device in devices:
        if "blackhole" in device.lower():
            return device
    return devices[0] if devices else None
