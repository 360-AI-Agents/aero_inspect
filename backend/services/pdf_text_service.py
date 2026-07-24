import os

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader


class PdfTextService:

    @staticmethod
    def extract_text(file_path: str) -> str:
        if not file_path.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are supported for text extraction right now.")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)

        full_text = "\n\n".join(text_parts)
        return full_text