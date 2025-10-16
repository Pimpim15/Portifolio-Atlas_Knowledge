"""Utilitários para hashing e verificação de senhas."""

from typing import cast

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """Gera hash seguro para a senha informada."""

    return cast(str, _pwd_context.hash(password))


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """Verifica se a senha informada corresponde ao hash armazenado."""

    return cast(bool, _pwd_context.verify(raw_password, hashed_password))
