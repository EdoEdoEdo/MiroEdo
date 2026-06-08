"""
File parser: extract plain text from .pdf / .md / .txt uploads.

Mirrors MiroFish's parsing strategy:
- PDF: PyMuPDF (fitz) page-by-page text extraction
- Markdown / text: UTF-8 first, then charset-normalizer, then chardet,
  finally UTF-8 with errors=replace.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


class FileParseError(RuntimeError):
    """Raised when a file cannot be parsed."""


SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


def parse_file(path: PathLike) -> str:
    """Return plain text extracted from `path`. Raises FileParseError on failure."""
    p = Path(path)
    if not p.is_file():
        raise FileParseError(f"File not found: {p}")

    ext = p.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(p)
    if ext in {".md", ".markdown", ".txt"}:
        return _parse_text(p)
    raise FileParseError(
        f"Unsupported extension '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def parse_bytes(data: bytes, filename: str) -> str:
    """Parse raw bytes given the original filename (used for HTTP uploads)."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _parse_pdf_bytes(data)
    if ext in {".md", ".markdown", ".txt"}:
        return _decode_bytes(data)
    raise FileParseError(
        f"Unsupported extension '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
    )


# === Internal ===


def _parse_pdf(path: Path) -> str:
    return _parse_pdf_bytes(path.read_bytes())


def _parse_pdf_bytes(data: bytes) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover
        raise FileParseError("PyMuPDF (fitz) not installed") from exc

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise FileParseError(f"Failed to open PDF: {exc}") from exc

    try:
        parts = [page.get_text("text") for page in doc]
    finally:
        doc.close()

    text = "\n".join(parts).strip()
    if not text:
        raise FileParseError("PDF parsed but no extractable text (image-only?)")
    return text


def _parse_text(path: Path) -> str:
    return _decode_bytes(path.read_bytes())


def _decode_bytes(data: bytes) -> str:
    # 1) UTF-8
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass

    # 2) charset-normalizer
    try:
        from charset_normalizer import from_bytes

        result = from_bytes(data).best()
        if result is not None:
            return str(result)
    except ImportError:  # pragma: no cover
        pass

    # 3) chardet
    try:
        import chardet

        guess = chardet.detect(data)
        enc = guess.get("encoding") if guess else None
        if enc:
            return data.decode(enc, errors="replace")
    except ImportError:  # pragma: no cover
        pass

    # 4) Last resort
    return data.decode("utf-8", errors="replace")
