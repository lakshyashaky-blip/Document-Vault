import datetime
from functools import wraps

import bcrypt
import jwt
from flask import request, jsonify, current_app, g

from models import User

COOKIE_NAME = "vault_token"


# ---------- password hashing ----------

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------- JWT ----------

def issue_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow()
        + datetime.timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"]),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])


def decode_token(token: str):
    return jwt.decode(
        token,
        current_app.config["JWT_SECRET"],
        algorithms=[current_app.config["JWT_ALGORITHM"]],
    )


def set_auth_cookie(response, user_id: str):
    token = issue_token(user_id)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,          # not readable by JS -> mitigates XSS token theft
        secure=current_app.config["COOKIE_SECURE"],  # True in production (HTTPS only)
        samesite="Lax",         # mitigates CSRF on cross-site requests
        max_age=current_app.config["JWT_EXPIRY_HOURS"] * 3600,
        path="/",
    )
    return response


def clear_auth_cookie(response):
    response.set_cookie(COOKIE_NAME, "", expires=0, path="/")
    return response


# ---------- auth decorator ----------

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        token = request.cookies.get(COOKIE_NAME)
        if not token:
            return jsonify({"error": "Not authenticated"}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired, please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid session"}), 401

        user = User.query.get(payload["sub"])
        if not user:
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        return view_func(*args, **kwargs)

    return wrapped
