from __future__ import annotations

from io import BytesIO
from pathlib import PurePath

from docx import Document
from pypdf import PdfReader

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


class StoryExtractionError(ValueError):
    pass


def safe_display_name(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name
    return name or "story"


def extract_story(filename: str, content: bytes, max_bytes: int) -> str:
    if not content:
        raise StoryExtractionError("The uploaded document is empty.")
    if len(content) > max_bytes:
        raise StoryExtractionError(f"The upload exceeds the {max_bytes // (1024 * 1024)} MB limit.")

    extension = PurePath(safe_display_name(filename)).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise StoryExtractionError("Unsupported file type. Upload a TXT, PDF, or DOCX document.")

    try:
        if extension == ".txt":
            text = content.decode("utf-8-sig")
        elif extension == ".pdf":
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if not text.strip():
                raise StoryExtractionError(
                    "No selectable text was found. This may be a scanned PDF; OCR is not yet included."
                )
        else:
            document = Document(BytesIO(content))
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except StoryExtractionError:
        raise
    except (UnicodeDecodeError, OSError, ValueError, KeyError) as exc:
        raise StoryExtractionError(f"Could not extract text from {extension[1:].upper()} document.") from exc

    text = text.strip()
    if not text:
        raise StoryExtractionError("The document contains no usable story text.")
    return text
