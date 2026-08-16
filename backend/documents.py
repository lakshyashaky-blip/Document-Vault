import os
import json
import uuid

from flask import Blueprint, request, jsonify, g, current_app, send_file
from werkzeug.utils import secure_filename

from extensions import db
from models import Document, Chunk
from utils.security import login_required
from utils.pdf_utils import extract_pages, chunk_text, PDFExtractionError
from utils.embeddings import embed_texts

documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


@documents_bp.post("")
@login_required
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Reject non-PDF by extension AND by content sniffing (magic bytes)
    if not _allowed_file(file.filename):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    header = file.stream.read(5)
    file.stream.seek(0)
    if header != b"%PDF-":
        return jsonify({"error": "File does not appear to be a valid PDF"}), 400

    # Enforce size limit explicitly (Flask's MAX_CONTENT_LENGTH also guards this globally)
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    max_size = current_app.config["MAX_CONTENT_LENGTH"]
    if size > max_size:
        return jsonify({"error": f"File exceeds the {max_size // (1024*1024)} MB limit"}), 400

    user = g.current_user
    user_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], user.id)
    os.makedirs(user_folder, exist_ok=True)

    safe_name = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4()}_{safe_name}"
    storage_path = os.path.join(user_folder, stored_name)
    file.save(storage_path)

    try:
        pages, page_count = extract_pages(storage_path)
    except PDFExtractionError as exc:
        os.remove(storage_path)
        return jsonify({"error": str(exc)}), 400

    doc = Document(
        user_id=user.id,
        filename=safe_name,
        storage_path=storage_path,
        file_size=size,
        page_count=page_count,
        pages_json=json.dumps(pages),
    )
    db.session.add(doc)
    db.session.flush()  # get doc.id before commit

    # Build RAG chunks + embeddings for this document
    raw_chunks = chunk_text(
        pages,
        chunk_size=current_app.config["CHUNK_SIZE"],
        overlap=current_app.config["CHUNK_OVERLAP"],
    )
    if raw_chunks:
        vectors = embed_texts([c["text"] for c in raw_chunks])
        for c, vec in zip(raw_chunks, vectors):
            db.session.add(
                Chunk(
                    document_id=doc.id,
                    user_id=user.id,
                    page=c["page"],
                    chunk_index=c["chunk_index"],
                    text=c["text"],
                    embedding_json=json.dumps(vec),
                )
            )

    db.session.commit()
    return jsonify({"document": doc.to_dict()}), 201


@documents_bp.get("")
@login_required
def list_documents():
    docs = (
        Document.query.filter_by(user_id=g.current_user.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return jsonify({"documents": [d.to_dict() for d in docs]}), 200


def _get_owned_document_or_404(doc_id):
    """Fetch a document but ONLY if it belongs to the current user.
    Returns None if it doesn't exist OR belongs to someone else — callers
    must treat both cases identically (404) so IDs can't be enumerated."""
    return Document.query.filter_by(id=doc_id, user_id=g.current_user.id).first()


@documents_bp.get("/<doc_id>")
@login_required
def get_document(doc_id):
    doc = _get_owned_document_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    return jsonify({"document": doc.to_dict(include_text=True)}), 200


@documents_bp.get("/<doc_id>/download")
@login_required
def download_document(doc_id):
    doc = _get_owned_document_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    if not os.path.exists(doc.storage_path):
        return jsonify({"error": "File missing from storage"}), 410
    return send_file(doc.storage_path, as_attachment=True, download_name=doc.filename)


@documents_bp.delete("/<doc_id>")
@login_required
def delete_document(doc_id):
    doc = _get_owned_document_or_404(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)

    db.session.delete(doc)  # cascades to Chunk rows
    db.session.commit()
    return jsonify({"message": "Document deleted"}), 200
