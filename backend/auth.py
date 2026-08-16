import re

from flask import Blueprint, request, jsonify, g

from extensions import db
from models import User
from utils.security import (
    hash_password,
    verify_password,
    set_auth_cookie,
    clear_auth_cookie,
    login_required,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not EMAIL_RE.match(email):
        return jsonify({"error": "Please provide a valid email address"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists"}), 409

    user = User(email=email, password_hash=hash_password(password))
    db.session.add(user)
    db.session.commit()

    resp = jsonify({"user": user.to_public_dict()})
    return set_auth_cookie(resp, user.id), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()
    if not user or not verify_password(password, user.password_hash):
        # Same message for both cases so we don't leak which emails are registered
        return jsonify({"error": "Invalid email or password"}), 401

    resp = jsonify({"user": user.to_public_dict()})
    return set_auth_cookie(resp, user.id), 200


@auth_bp.post("/logout")
def logout():
    resp = jsonify({"message": "Logged out"})
    return clear_auth_cookie(resp), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.current_user.to_public_dict()}), 200
