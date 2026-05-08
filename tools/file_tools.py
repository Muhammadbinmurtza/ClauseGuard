"""File parsing utilities for contract documents."""

import io
from typing import Union

import chardet


def read_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF.

    Falls back to pdfplumber if PyMuPDF extraction returns empty.

    Args:
        file_bytes: Raw bytes of the PDF file.

    Returns:
        Extracted text content as a string.

    Raises:
        ValueError: If the PDF cannot be read or contains no extractable text.
    """
    import fitz

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Unable to open PDF file: {e}") from e

    text_parts: list[str] = []
    for page in doc:
        text_parts.append(page.get_text())

    doc.close()
    result = "\n".join(text_parts).strip()

    if result:
        return result

    result = _read_pdf_with_pdfplumber(file_bytes)
    if result:
        return result

    raise ValueError("PDF file contains no extractable text — try pasting the text directly")


def _read_pdf_with_pdfplumber(file_bytes: bytes) -> str:
    """Fallback PDF extraction using pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        return ""

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text_parts: list[str] = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts).strip()
    except Exception:
        return ""


def read_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file using python-docx.

    Args:
        file_bytes: Raw bytes of the DOCX file.

    Returns:
        Extracted text content as a string.

    Raises:
        ValueError: If the DOCX cannot be read or contains no text.
    """
    from docx import Document

    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Unable to open DOCX file: {e}") from e

    paragraphs: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            paragraphs.append(para.text)

    result = "\n".join(paragraphs).strip()

    if not result:
        raise ValueError("DOCX file contains no extractable text")

    return result


def detect_encoding(file_bytes: bytes) -> str:
    """Detect the character encoding of a byte string using chardet.

    Args:
        file_bytes: Raw bytes to detect encoding for.

    Returns:
        Detected encoding name string (e.g., 'utf-8', 'latin-1').
    """
    detection = chardet.detect(file_bytes)
    return detection.get("encoding", "utf-8") or "utf-8"


def read_txt(file_bytes: bytes) -> str:
    """Read a plain text file with automatic encoding detection.

    Args:
        file_bytes: Raw bytes of the text file.

    Returns:
        Decoded text content as a string.

    Raises:
        ValueError: If the file cannot be decoded or is empty.
    """
    encoding = detect_encoding(file_bytes)

    try:
        text = file_bytes.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        text = file_bytes.decode("utf-8", errors="replace")

    result = text.strip()

    if not result:
        raise ValueError("Text file is empty or contains no readable content")

    return result


SUPPORTED_EXTENSIONS = frozenset({".pdf", ".txt", ".docx"})
READER_MAP = {
    ".pdf": read_pdf,
    ".txt": read_txt,
    ".docx": read_docx,
}


def extract_text(file_bytes: bytes, filename: str) -> str:
    """Route file to the appropriate reader based on extension.

    Args:
        file_bytes: Raw bytes of the file.
        filename: Original filename used to determine file type.

    Returns:
        Extracted text content as a string.

    Raises:
        ValueError: If the file extension is not supported or the file is unreadable.
    """
    if not filename:
        raise ValueError("Filename is required to determine file type")

    ext = _get_extension(filename)

    if ext not in READER_MAP:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported types: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    reader = READER_MAP[ext]
    return reader(file_bytes)


def _get_extension(filename: str) -> str:
    """Extract the lowercase file extension from a filename."""
    dot_index = filename.rfind(".")
    if dot_index == -1 or dot_index == len(filename) - 1:
        raise ValueError(f"Cannot determine file type from filename: {filename}")
    return filename[dot_index:].lower()
