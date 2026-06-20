from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UploadedFile:
    filename: str
    data: bytes


@dataclass
class MultipartForm:
    fields: dict[str, str]
    files: dict[str, UploadedFile]


def parse_multipart(body: bytes, content_type: str) -> MultipartForm:
    if "boundary=" not in content_type:
        raise ValueError("expected multipart form data")

    boundary = content_type.split("boundary=", 1)[1].strip().strip('"')
    delimiter = f"--{boundary}".encode()
    fields: dict[str, str] = {}
    files: dict[str, UploadedFile] = {}

    for part in body.split(delimiter):
        if not part or part in (b"--", b"--\r\n"):
            continue
        part = part.lstrip(b"\r\n")
        if not part.strip():
            continue

        header_block, _, content = part.partition(b"\r\n\r\n")
        if not _:
            continue

        headers = header_block.decode("utf-8", errors="replace")
        name = _header_value(headers, "name")
        if name is None:
            continue

        filename = _header_value(headers, "filename")
        payload = content.rstrip(b"\r\n")
        if filename:
            files[name] = UploadedFile(filename=filename, data=payload)
        else:
            fields[name] = payload.decode("utf-8")

    return MultipartForm(fields=fields, files=files)


def _header_value(headers: str, key: str) -> str | None:
    prefix = f'{key}="'
    for line in headers.split("\r\n"):
        if "Content-Disposition:" not in line:
            continue
        for token in line.split(";"):
            token = token.strip()
            if token.startswith(prefix) and token.endswith('"'):
                return token[len(prefix) : -1]
    return None
