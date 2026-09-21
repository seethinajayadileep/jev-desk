"""Read a CSV, text file, or PDF into the one customer message.

The file is not stored. Its text is the message, and that message is still
one system_one call.
"""

import csv
import io
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default as email_policy
from pathlib import Path

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 20
MAX_CSV_ROWS = 200

_TEXT_SUFFIXES = {".txt", ".text"}


class UploadError(Exception):
    """The file can be explained on the page. Jev is not called."""


@dataclass(frozen=True)
class Submission:
    message: str
    filename: str | None = None
    data: bytes | None = None


def display_name(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name.replace("\x00", "") if ch.isprintable()).strip()
    return name[:120] or "upload"


def parse_submission(content_type: str, body: bytes) -> Submission:
    media = (content_type or "").split(";", 1)[0].strip().lower()
    if media == "multipart/form-data":
        return _multipart(content_type, body)
    text = body.decode("utf-8", errors="replace")
    from urllib.parse import parse_qs

    message = (parse_qs(text, keep_blank_values=True).get("message") or [""])[0]
    return Submission(message=message)


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadError("That file is too large.")
    kind = _kind(filename, data)
    if kind == "pdf":
        text = _pdf_text(data)
    elif kind == "csv":
        text = _csv_text(data)
    else:
        text = _plain_text(data)
    text = text.replace("\x00", "").strip()
    if not text:
        raise UploadError("That file has no message text.")
    return text


def _kind(filename: str, data: bytes) -> str:
    suffix = Path(display_name(filename)).suffix.lower()
    if suffix == ".pdf" or (not suffix and data.startswith(b"%PDF")):
        if not data.startswith(b"%PDF"):
            raise UploadError("That PDF could not be read.")
        return "pdf"
    if suffix == ".csv":
        return "csv"
    if suffix in _TEXT_SUFFIXES:
        return "txt"
    raise UploadError("Upload a CSV, text, or PDF file.")


def _decode(data: bytes) -> str:
    if b"\x00" in data:
        raise UploadError("That file could not be read.")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _plain_text(data: bytes) -> str:
    return _decode(data)


def _csv_text(data: bytes) -> str:
    try:
        raw = _decode(data)
        sample = raw[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            if not getattr(dialect, "delimiter", ""):
                dialect = csv.excel
        except csv.Error:
            dialect = csv.excel
        rows: list[list[str]] = []
        for index, row in enumerate(csv.reader(io.StringIO(raw), dialect)):
            if index > MAX_CSV_ROWS:
                raise UploadError("That CSV has too many rows to sort as one message.")
            cells = [cell.strip() for cell in row]
            if any(cells):
                rows.append(cells)
    except UploadError:
        raise
    except csv.Error as exc:
        raise UploadError("That CSV could not be read.") from exc
    if not rows:
        return ""
    if len(rows) >= 2 and _header_row(rows[0]):
        headers = rows[0]
        blocks = []
        for record in rows[1:]:
            lines = []
            for index, header in enumerate(headers):
                value = record[index].strip() if index < len(record) else ""
                if value:
                    lines.append(f"{header}: {value}")
            for value in record[len(headers) :]:
                if value.strip():
                    lines.append(value.strip())
            if lines:
                blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
    lines = []
    for row in rows:
        kept = [cell for cell in row if cell]
        if kept:
            lines.append(", ".join(kept))
    return "\n\n".join(lines)


def _header_row(row: list[str]) -> bool:
    if not row or any(not cell for cell in row):
        return False
    return all(len(cell) <= 40 for cell in row)


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise UploadError("That PDF could not be read.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:
                raise UploadError("That PDF is password protected.") from exc
            if not unlocked:
                raise UploadError("That PDF is password protected.")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UploadError("That PDF has too many pages to sort as one message.")
        chunks = []
        for index, page in enumerate(reader.pages):
            if index >= MAX_PDF_PAGES:
                break
            chunks.append(page.extract_text() or "")
    except UploadError:
        raise
    except Exception as exc:
        raise UploadError("That PDF could not be read.") from exc
    return "\n\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())


def _multipart(content_type: str, body: bytes) -> Submission:
    boundary = _boundary(content_type)
    message = ""
    filename: str | None = None
    data: bytes | None = None
    for head, payload in _parts(body, boundary):
        name, file_name = _part_fields(head)
        if name == "message":
            message = payload.decode("utf-8", errors="replace")
        elif name == "upload" and (file_name or payload):
            filename = file_name or "upload"
            data = payload
    return Submission(message=message, filename=filename, data=data)


def _boundary(content_type: str) -> bytes:
    header = f"Content-Type: {content_type}\r\n\r\n".encode("utf-8", errors="replace")
    parsed = BytesParser(policy=email_policy).parsebytes(header)
    boundary = parsed.get_boundary()
    if not boundary or len(boundary) > 200:
        raise UploadError("That upload could not be read.")
    try:
        raw = boundary.encode("ascii")
    except UnicodeEncodeError:
        raise UploadError("That upload could not be read.") from None
    return raw


def _parts(body: bytes, boundary: bytes):
    marker = b"--" + boundary
    for piece in body.split(marker)[1:]:
        if piece.startswith(b"--"):
            return
        if piece.startswith(b"\r\n"):
            piece = piece[2:]
        elif piece.startswith(b"\n"):
            piece = piece[1:]
        if piece.endswith(b"\r\n"):
            piece = piece[:-2]
        elif piece.endswith(b"\n"):
            piece = piece[:-1]
        head, sep, payload = piece.partition(b"\r\n\r\n")
        if not sep:
            head, sep, payload = piece.partition(b"\n\n")
        if not sep or len(head) > 8192:
            raise UploadError("That upload could not be read.")
        yield head, payload


def _part_fields(head: bytes) -> tuple[str | None, str | None]:
    parsed = BytesParser(policy=email_policy).parsebytes(head + b"\r\n\r\n")
    name = parsed.get_param("name", header="content-disposition")
    if isinstance(name, tuple):
        name = name[-1]
    filename = parsed.get_filename()
    if isinstance(name, str):
        name = name.strip() or None
    else:
        name = None
    return name, filename
