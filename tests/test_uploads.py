from io import BytesIO
from zipfile import ZipFile

import pytest

from company_compass.utils.uploads import extract_document


def test_plain_text_upload_preserves_readable_content():
    assert extract_document("overview.md", b"# Overview\n\nCompany services.") == (
        "# Overview\n\nCompany services."
    )


def test_docx_upload_extracts_paragraphs_without_writing_zip_files():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>Company overview</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Services and products.</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
    assert extract_document("overview.docx", buffer.getvalue()) == (
        "Company overview\nServices and products."
    )


def test_unsupported_or_empty_upload_is_not_silently_ingested():
    with pytest.raises(ValueError, match="(?i)supported"):
        extract_document("program.exe", b"content")
    with pytest.raises(ValueError, match="readable"):
        extract_document("empty.txt", b" \n ")
    with pytest.raises(ValueError, match="UTF-8"):
        extract_document("bad.txt", b"\xff\xfe\x00")


def test_pdf_with_no_extractable_text_requests_text_document():
    from pypdf import PdfWriter

    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(300, 300)
    writer.write(buffer)
    with pytest.raises(ValueError, match="readable"):
        extract_document("scan.pdf", buffer.getvalue())
