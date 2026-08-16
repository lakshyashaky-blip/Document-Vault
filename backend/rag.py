from flask import Blueprint, request, jsonify, g, current_app

from models import Chunk
from utils.security import login_required
from utils.embeddings import embed_query, cosine_search

rag_bp = Blueprint("rag", __name__, url_prefix="/api/rag")


SYSTEM_PROMPT = """You are a helpful assistant answering questions about a user's uploaded \
documents. You will be given several excerpts retrieved from those documents, each tagged \
with the source filename and page number.

Rules:
- Answer ONLY using the information in the provided excerpts.
- If the excerpts don't contain enough information to answer, say so plainly — do not guess \
or use outside knowledge.
- Cite the filename and page number for every claim you make, like this: (source.pdf, p. 3).
- Keep answers concise and directly responsive to the question.
"""


def _build_context(chunks_with_scores, doc_lookup):
    blocks = []
    for chunk, score in chunks_with_scores:
        fname = doc_lookup[chunk.document_id]
        blocks.append(f"[Source: {fname}, page {chunk.page}]\n{chunk.text}")
    return "\n\n---\n\n".join(blocks)


def _generate_answer(prompt_text):
    """
    Calls whichever provider is configured, in this priority order:
    1. Anthropic (if ANTHROPIC_API_KEY is set) — paid, highest quality.
    2. Groq (if GROQ_API_KEY is set) — genuinely free, no card required,
       console.groq.com/keys. Runs open-weight models on fast inference hardware.
    3. Gemini (if GEMINI_API_KEY is set) — free tier via Google AI Studio,
       aistudio.google.com/apikey.
    """
    if current_app.config["ANTHROPIC_API_KEY"]:
        import anthropic
        client = anthropic.Anthropic(api_key=current_app.config["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=current_app.config["ANTHROPIC_MODEL"],
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )

    if current_app.config["GROQ_API_KEY"]:
        from groq import Groq
        client = Groq(api_key=current_app.config["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model=current_app.config["GROQ_MODEL"],
            max_tokens=1000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text},
            ],
        )
        return response.choices[0].message.content

    if current_app.config["GEMINI_API_KEY"]:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=current_app.config["GEMINI_API_KEY"])
        response = client.models.generate_content(
            model=current_app.config["GEMINI_MODEL"],
            contents=prompt_text,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1000,
            ),
        )
        return response.text

    raise RuntimeError("No LLM provider configured")


@rag_bp.post("/ask")
@login_required
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    document_id = data.get("document_id")  # optional: scope to one document

    if not question:
        return jsonify({"error": "Question is required"}), 400

    if not current_app.config["ANTHROPIC_API_KEY"] and not current_app.config["GROQ_API_KEY"] and not current_app.config["GEMINI_API_KEY"]:
        return jsonify({
            "error": "RAG answering is not configured on this server. "
                     "Set ANTHROPIC_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY in the backend .env file."
        }), 503

    query = Chunk.query.filter_by(user_id=g.current_user.id)
    if document_id:
        query = query.filter_by(document_id=document_id)
    candidate_chunks = query.all()

    if not candidate_chunks:
        return jsonify({
            "answer": "You don't have any processed documents to search yet. "
                      "Upload a PDF first.",
            "sources": [],
        }), 200

    query_vector = embed_query(question)
    top_chunks = cosine_search(query_vector, candidate_chunks, top_k=current_app.config["TOP_K"])

    # Map document_id -> filename for citations, scoped to this user only
    doc_ids = {c.document_id for c, _ in top_chunks}
    from models import Document
    docs = Document.query.filter(
        Document.id.in_(doc_ids), Document.user_id == g.current_user.id
    ).all()
    doc_lookup = {d.id: d.filename for d in docs}

    context = _build_context(top_chunks, doc_lookup)

    try:
        answer_text = _generate_answer(f"Excerpts:\n\n{context}\n\nQuestion: {question}")
    except Exception as exc:
        return jsonify({"error": f"Failed to generate an answer: {exc}"}), 502

    sources = [
        {
            "document_id": chunk.document_id,
            "filename": doc_lookup.get(chunk.document_id, "unknown"),
            "page": chunk.page,
            "score": round(score, 4),
            "excerpt": chunk.text[:300],
        }
        for chunk, score in top_chunks
    ]

    return jsonify({"answer": answer_text, "sources": sources}), 200
