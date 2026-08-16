import uuid
import datetime
import json

from extensions import db


def gen_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    documents = db.relationship(
        "Document", backref="owner", lazy=True, cascade="all, delete-orphan"
    )

    def to_public_dict(self):
        return {"id": self.id, "email": self.email}


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    filename = db.Column(db.String(500), nullable=False)
    storage_path = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    page_count = db.Column(db.Integer, nullable=False, default=0)

    # Full extracted text, stored as JSON list of {page, text}
    pages_json = db.Column(db.Text, nullable=False, default="[]")

    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    chunks = db.relationship(
        "Chunk", backref="document", lazy=True, cascade="all, delete-orphan"
    )

    def full_text(self):
        pages = json.loads(self.pages_json)
        return "\n\n".join(p["text"] for p in pages)

    def to_dict(self, include_text=False):
        data = {
            "id": self.id,
            "filename": self.filename,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "uploaded_at": self.uploaded_at.isoformat() + "Z",
        }
        if include_text:
            data["pages"] = json.loads(self.pages_json)
        return data


class Chunk(db.Model):
    """A slice of a document's text with a cached embedding, used for RAG retrieval."""

    __tablename__ = "chunks"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    document_id = db.Column(db.String(36), db.ForeignKey("documents.id"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    page = db.Column(db.Integer, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)

    # embedding vector serialized as JSON list of floats
    embedding_json = db.Column(db.Text, nullable=False)

    def embedding(self):
        return json.loads(self.embedding_json)
