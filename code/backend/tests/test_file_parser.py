"""Tests for ingestion.file_parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.file_parser import FileParseError, parse_bytes, parse_file


def test_parse_txt_utf8(tmp_path: Path) -> None:
    p = tmp_path / "note.txt"
    p.write_text("Mulino Bianco — colazione italiana", encoding="utf-8")
    assert "Mulino Bianco" in parse_file(p)


def test_parse_md_utf8(tmp_path: Path) -> None:
    p = tmp_path / "brief.md"
    p.write_text("# Brand\n\nBarilla è leader.\n", encoding="utf-8")
    out = parse_file(p)
    assert "Barilla" in out and "leader" in out


def test_parse_text_latin1(tmp_path: Path) -> None:
    # Use a longer sample so charset detection can lock onto latin-1.
    sample = (
        "Caffè è già pronto. La colazione italiana è composta da cornetto, "
        "biscotti e cappuccino. È un'abitudine quotidiana per la maggior parte "
        "degli italiani, da nord a sud."
    ) * 3
    p = tmp_path / "legacy.txt"
    p.write_bytes(sample.encode("latin-1"))
    out = parse_file(p)
    assert "Caff" in out and "colazione" in out


def test_parse_bytes_md() -> None:
    out = parse_bytes(b"# Hello", "x.md")
    assert "Hello" in out


def test_unsupported_extension(tmp_path: Path) -> None:
    p = tmp_path / "x.docx"
    p.write_bytes(b"\x00")
    with pytest.raises(FileParseError):
        parse_file(p)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileParseError):
        parse_file(tmp_path / "nope.txt")


def test_parse_pdf_real(tmp_path: Path) -> None:
    """Build a tiny PDF on-the-fly via PyMuPDF and round-trip the text."""
    fitz = pytest.importorskip("fitz")
    p = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Mulino Bianco snapshot report")
    doc.save(str(p))
    doc.close()

    out = parse_file(p)
    assert "Mulino Bianco" in out


def test_parse_pdf_image_only_raises(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    p = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()  # blank page, no text
    doc.save(str(p))
    doc.close()

    with pytest.raises(FileParseError):
        parse_file(p)
