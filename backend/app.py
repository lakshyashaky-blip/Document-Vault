import os

from flask import Flask, send_from_directory
from flask_cors import CORS

from config import Config
from extensions import db
from auth import auth_bp
from documents import documents_bp
from rag import rag_bp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)

    os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Cookies carry the session, so we need credentials + a concrete origin (not "*")
    CORS(app, supports_credentials=True, origins=["http://localhost:5000", "http://127.0.0.1:5000"])

    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(rag_bp)

    # Serve the plain HTML/JS frontend from the same origin (simplifies cookie handling)
    def _no_store_html(response):
        # HTML pages check auth on load via JS. If the browser bfcaches one
        # (e.g. restoring it on back/forward navigation) that JS never re-runs,
        # so a page can keep showing a logged-in view after logout. Marking
        # HTML responses no-store keeps them out of that cache entirely.
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return _no_store_html(send_from_directory(FRONTEND_DIR, "landing.html"))

    @app.get("/<path:path>")
    def frontend_files(path):
        full_path = os.path.join(FRONTEND_DIR, path)
        if os.path.isfile(full_path):
            resp = send_from_directory(FRONTEND_DIR, path)
            return _no_store_html(resp) if path.endswith(".html") else resp
        return _no_store_html(send_from_directory(FRONTEND_DIR, "landing.html"))

    @app.errorhandler(413)
    def too_large(e):
        return {"error": "File exceeds the 20 MB limit"}, 413

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
