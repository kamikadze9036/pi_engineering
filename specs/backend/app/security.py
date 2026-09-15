import hashlib
import hmac
import os
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import User


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(expected, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Přihlaste se.")
    return user


def writer(user: User = Depends(current_user)) -> User:
    if user.role not in ("ENGINEER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Nemáte oprávnění k úpravě.")
    return user


def approver(user: User = Depends(current_user)) -> User:
    if user.role not in ("APPROVER", "ADMIN"):
        raise HTTPException(status_code=403, detail="Schválení vyžaduje roli schvalovatele.")
    return user


def administrator(user: User = Depends(current_user)) -> User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Tato operace vyžaduje administrátora.")
    return user
