from __future__ import annotations

from io import BytesIO

from docx import Document


def build_docx_resume(resume_text: str) -> bytes:
    document = Document()

    for line in resume_text.splitlines():
        clean_line = line.rstrip()
        if clean_line:
            document.add_paragraph(clean_line)
        else:
            document.add_paragraph("")

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()
