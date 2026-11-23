from io import BytesIO

import pytest
from docx import Document

from app.services.story_parser import StoryExtractionError, extract_story, safe_display_name


def test_extracts_utf8_txt():
    assert extract_story("fox.txt", b"A fox walks.", 100) == "A fox walks."


def test_rejects_unsupported_and_oversized_files():
    with pytest.raises(StoryExtractionError, match="Unsupported"):
        extract_story("story.exe", b"no", 100)
    with pytest.raises(StoryExtractionError, match="exceeds"):
        extract_story("story.txt", b"123", 2)


def test_sanitizes_filename():
    assert safe_display_name(r"..\..\story.txt") == "story.txt"


def test_extracts_docx():
    stream = BytesIO()
    document = Document()
    document.add_paragraph("The fox finds a stone.")
    document.save(stream)
    assert extract_story("story.docx", stream.getvalue(), 100_000) == "The fox finds a stone."
