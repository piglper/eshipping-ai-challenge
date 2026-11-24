"""Text extraction from PDF attachments (``DocumentParser``).

Only the text layer is read. A PDF without text (a scan) is reported with
``has_text_layer=False`` so that it can be routed to OCR; OCR itself is not applied in the
PoC (docs/10_diseno_poc.md §2).
"""

import logging
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from eshipping_ai.domain.ports import ParsedDocument

# pypdf warns about fonts it cannot fully decode even when the text is read correctly.
logging.getLogger("pypdf").setLevel(logging.ERROR)

MIN_TEXT_CHARS = 20
"""Below this many non-blank characters a PDF is considered to have no text layer."""


class PdfTextParser:
    """Reads the text layer of PDF files; any other file type has no text."""

    def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """Extract the text of an attachment.

        Args:
            content: Bytes of the file.
            filename: Name of the file; only ``.pdf`` files are read.

        Returns:
            The text and whether it came from a text layer. Unreadable or non-PDF files
            come back without text.
        """
        if not filename.lower().endswith(".pdf"):
            return ParsedDocument(text=None, has_text_layer=False, pages=0)
        try:
            reader = PdfReader(BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
        except PyPdfError, ValueError, KeyError:
            return ParsedDocument(text=None, has_text_layer=False, pages=0)
        text = "\n\n".join(pages).strip()
        has_text = len("".join(text.split())) >= MIN_TEXT_CHARS
        return ParsedDocument(
            text=text if has_text else None, has_text_layer=has_text, pages=len(pages)
        )
