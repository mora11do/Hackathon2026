"""
Extract text from a one-page resume PDF and print it.

Setup:   pip install pypdf
Usage:   python extract_resume.py resume.pdf
"""

import sys
from pypdf import PdfReader

MAX_PAGES = 2           # a resume should be 1 page; allow a little slack
MIN_TEXT_LENGTH = 100   # below this, the PDF is probably a scan


def extract_text(path):
    reader = PdfReader(path)

    if reader.is_encrypted:
        raise ValueError("This PDF is password-protected.")

    if len(reader.pages) > MAX_PAGES:
        raise ValueError(
            f"PDF has {len(reader.pages)} pages; expected at most {MAX_PAGES}."
        )

    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def main():
    if len(sys.argv) != 2:
        print("Usage: python extract_resume.py resume.pdf")
        sys.exit(1)

    path = sys.argv[1]

    try:
        text = extract_text(path)
    except FileNotFoundError:
        print(f"File not found: {path}")
        sys.exit(1)
    except Exception as e:
        print(f"Could not read PDF: {e}")
        sys.exit(1)

    if len(text) < MIN_TEXT_LENGTH:
        print("Very little text was found. This may be a scanned PDF (an image),")
        print("which needs OCR or Claude's direct PDF reading instead.")
        print(f"\nWhat was extracted ({len(text)} characters):\n{text}")
        sys.exit(1)

    print(f"Extracted {len(text)} characters:\n")
    print("-" * 40)
    print(text)
    print("-" * 40)


if __name__ == "__main__":
    main()
