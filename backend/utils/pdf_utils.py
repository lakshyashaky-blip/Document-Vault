from pypdf import PdfReader


class PDFExtractionError(Exception):
    pass


def extract_pages(file_path: str):
    """
    Returns a list of {"page": int, "text": str} for every page in the PDF,
    plus the total page count.
    """
    try:
        reader = PdfReader(file_path)
    except Exception as exc:
        raise PDFExtractionError(f"Could not read PDF: {exc}")

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise PDFExtractionError("PDF is password-protected and could not be opened")

    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append({"page": i + 1, "text": text.strip()})

    return pages, len(reader.pages)


def chunk_text(pages, chunk_size=800, overlap=150):
    """
    Splits page text into overlapping character chunks for embedding/retrieval.
    Each chunk keeps track of which page it came from.
    Returns list of {"page": int, "chunk_index": int, "text": str}
    """
    chunks = []
    global_index = 0
    for p in pages:
        text = p["text"]
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end].strip()
            if piece:
                chunks.append({"page": p["page"], "chunk_index": global_index, "text": piece})
                global_index += 1
            if end == len(text):
                break
            start = end - overlap
    return chunks
