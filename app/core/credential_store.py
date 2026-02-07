"""
Encrypted credential store — Fernet-based encryption for integration secrets.

The encryption key is derived from ``CREDENTIAL_ENCRYPTION_KEY`` env var
(must be a url-safe base64-encoded 32-byte key — generate with
``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``).

Usage::

    from app.core.credential_store import credential_store

    # Encrypt & persist
    credential_store.set(session, integration_id, "access_token", "sk-live-...")

    # Decrypt & retrieve
    plain = credential_store.get(session, integration_id, "access_token")
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


class CredentialStore:
    """Fernet-based encrypt/decrypt store backed by IntegrationCredential rows."""

    def __init__(self) -> None:
        self._fernet: Fernet | None = None

    @property
    def fernet(self) -> Fernet:
        """Lazy-init Fernet from env var (fail-fast in production)."""
        if self._fernet is None:
            key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
            if not key:
                raise RuntimeError(
                    "CREDENTIAL_ENCRYPTION_KEY env var is required. "
                    "Generate one with: python -c "
                    "'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            self._fernet = Fernet(key.encode())
        return self._fernet

    # ── encrypt / decrypt primitives ──

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string → base64-encoded ciphertext."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext → plaintext string."""
        try:
            return self.fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt credential — invalid key or corrupted data")
            raise

    # ── DB-backed CRUD ──

    def set(
        self,
        session: Session,
        integration_id: int,
        key: str,
        value: str,
        *,
        expires_at: datetime | None = None,
        tenant_id=None,
    ) -> None:
        """Encrypt & upsert a credential."""
        from app.models.integration_models import IntegrationCredential

        stmt = select(IntegrationCredential).where(
            IntegrationCredential.integration_id == integration_id,
            IntegrationCredential.key == key,
        )
        cred = session.exec(stmt).first()

        encrypted = self.encrypt(value)

        if cred:
            cred.encrypted_value = encrypted
            cred.expires_at = expires_at
        else:
            cred = IntegrationCredential(
                integration_id=integration_id,
                key=key,
                encrypted_value=encrypted,
                expires_at=expires_at,
                tenant_id=tenant_id,
            )
            session.add(cred)
        session.flush()

    def get(
        self,
        session: Session,
        integration_id: int,
        key: str,
    ) -> str | None:
        """Retrieve & decrypt a credential, or ``None`` if not found."""
        from app.models.integration_models import IntegrationCredential

        stmt = select(IntegrationCredential).where(
            IntegrationCredential.integration_id == integration_id,
            IntegrationCredential.key == key,
        )
        cred = session.exec(stmt).first()
        if cred is None:
            return None
        return self.decrypt(cred.encrypted_value)

    def delete(
        self,
        session: Session,
        integration_id: int,
        key: str,
    ) -> bool:
        """Delete a credential. Returns ``True`` if it existed."""
        from app.models.integration_models import IntegrationCredential

        stmt = select(IntegrationCredential).where(
            IntegrationCredential.integration_id == integration_id,
            IntegrationCredential.key == key,
        )
        cred = session.exec(stmt).first()
        if cred:
            session.delete(cred)
            session.flush()
            return True
        return False


# Module-level singleton
credential_store = CredentialStore()
