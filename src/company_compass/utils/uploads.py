"""Bounded text extraction for administrator-uploaded company documents."""

from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

MAX_UPLOAD_BYTES = 10_000_000
MAX_TEXT_BYTES = 2_000_000
SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


def extract_document(filename: str, payload: bytes) -> str:
    """Extract plain text; no temporary files, scripts, remote links or OCR."""
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Supported document types are TXT, Markdown, PDF and DOCX")
    if not payload or len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("Upload a nonempty document of at most 10 MB")
    if extension in {".txt", ".md"}:
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("Text and Markdown documents must use UTF-8 encoding") from None
    elif extension == ".pdf":
        text = _pdf_text(payload)
    else:
        text = _docx_text(payload)
    if not text.strip():
        raise ValueError("The document contains no readable text; scanned PDFs require OCR")
    if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
        raise ValueError("Extracted document text must be at most 2 MB")
    return text


def _pdf_text(payload: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(payload))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("Upload an unlocked PDF")
        if len(reader.pages) > 100:
            raise ValueError("PDF documents are limited to 100 pages")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except ValueError:
        raise
    except Exception:
        raise ValueError("The PDF could not be read. Upload a valid text-based PDF") from None


def _docx_text(payload: bytes) -> str:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 20_000_000:
                raise ValueError("The expanded DOCX document exceeds the size limit")
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join(
            "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
            for paragraph in root.findall(".//w:p", namespace)
        )
    except (BadZipFile, KeyError, ElementTree.ParseError):
        raise ValueError("The DOCX document could not be read") from None
