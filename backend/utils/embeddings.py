"""
Embedding helper for the RAG pipeline.

Uses sentence-transformers (local, no API key needed) to embed chunk text
and query text, and plain numpy cosine similarity for retrieval. This keeps
the project runnable without any external vector DB — for larger scale,
swap `search_similar` below for a FAISS / pgvector / Pinecone index.
"""
import json
import numpy as np

_model = None


def get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        from flask import current_app
        _model = SentenceTransformer(current_app.config["EMBEDDING_MODEL"])
    return _model


def embed_texts(texts):
    model = get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_query(text):
    model = get_model()
    vector = model.encode([text], normalize_embeddings=True)[0]
    return vector


def cosine_search(query_vector, chunks, top_k=5):
    """
    chunks: list of Chunk model instances (already filtered to the right user/document).
    Returns the top_k chunks sorted by similarity, each paired with its score.
    """
    if not chunks:
        return []

    matrix = np.array([json.loads(c.embedding_json) for c in chunks])
    query = np.array(query_vector)

    # vectors are already normalized at embed time -> dot product = cosine similarity
    scores = matrix @ query
    order = np.argsort(-scores)[:top_k]

    return [(chunks[i], float(scores[i])) for i in order]
