"""
Credential Manager
==================

Phase 39A: Secure credential storage with encryption at rest.

Uses AES-256-GCM encryption with PBKDF2 key derivation from admin password.
Credentials are stored in data/credentials.enc and survive server restarts.

Security Features:
- PBKDF2 key derivation (100,000 iterations, SHA256)
- AES-256-GCM authenticated encryption
- Random salt per encryption (stored in file header)
- Atomic writes (temp file + rename) to prevent corruption
- Never logs actual credential values
"""

import os
import json
import base64
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Check if cryptography is available
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    logger.warning("[CREDENTIALS] cryptography package not installed. Encrypted storage disabled.")


# Constants
CREDENTIALS_FILE = "data/credentials.enc"
PBKDF2_ITERATIONS = 100_000
SALT_LENGTH = 16
NONCE_LENGTH = 12
SCHEMA_VERSION = 1


@dataclass
class CredentialEntry:
    """Single credential entry with metadata."""
    value: str
    credential_type: str = "api_key"  # "api_key" | "service_account_json"
    updated_at: str = ""
    updated_by: str = "admin"

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = datetime.utcnow().isoformat() + "Z"


class CredentialManager:
    """
    Secure credential storage with encryption at rest.

    Usage:
        manager = CredentialManager(admin_password)
        manager.save_credential("openai_api_key", "sk-...", "api_key")
        key = manager.load_credential("openai_api_key")
        manager.apply_to_environment()  # Load all to os.environ
    """

    def __init__(self, admin_password: str, base_dir: Optional[Path] = None):
        """
        Initialize credential manager.

        Args:
            admin_password: Admin password for key derivation
            base_dir: Base directory for credentials file (default: module dir)
        """
        self._password = admin_password
        self._base_dir = base_dir or Path(__file__).parent
        self._credentials_path = self._base_dir / CREDENTIALS_FILE
        self._encryption_available = HAS_CRYPTOGRAPHY

        # In-memory cache
        self._cache: Optional[Dict[str, CredentialEntry]] = None

        # Ensure data directory exists
        self._credentials_path.parent.mkdir(parents=True, exist_ok=True)

    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive encryption key from password using PBKDF2.

        Args:
            salt: Random salt for key derivation

        Returns:
            32-byte key for AES-256
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package required for credential encryption")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
            backend=default_backend()
        )
        return kdf.derive(self._password.encode('utf-8'))

    def _encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using AES-256-GCM.

        Format: salt (16) + nonce (12) + ciphertext (N) + tag (16)

        Args:
            data: Plaintext bytes to encrypt

        Returns:
            Encrypted bytes with salt and nonce prepended
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package required for credential encryption")

        # Generate random salt and nonce
        salt = os.urandom(SALT_LENGTH)
        nonce = os.urandom(NONCE_LENGTH)

        # Derive key and encrypt
        key = self._derive_key(salt)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)  # No associated data

        return salt + nonce + ciphertext

    def _decrypt(self, data: bytes) -> bytes:
        """
        Decrypt data using AES-256-GCM.

        Args:
            data: Encrypted bytes (salt + nonce + ciphertext + tag)

        Returns:
            Decrypted plaintext bytes
        """
        if not HAS_CRYPTOGRAPHY:
            raise RuntimeError("cryptography package required for credential encryption")

        if len(data) < SALT_LENGTH + NONCE_LENGTH + 16:  # 16 = tag length
            raise ValueError("Invalid encrypted data: too short")

        # Extract components
        salt = data[:SALT_LENGTH]
        nonce = data[SALT_LENGTH:SALT_LENGTH + NONCE_LENGTH]
        ciphertext = data[SALT_LENGTH + NONCE_LENGTH:]

        # Derive key and decrypt
        key = self._derive_key(salt)
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    def _load_all(self) -> Dict[str, CredentialEntry]:
        """
        Load and decrypt all credentials from file.

        Returns:
            Dict of credential_id -> CredentialEntry
        """
        if self._cache is not None:
            return self._cache

        if not self._credentials_path.exists():
            self._cache = {}
            return self._cache

        try:
            # Read encrypted file
            encrypted_data = self._credentials_path.read_bytes()

            # Decrypt
            decrypted = self._decrypt(encrypted_data)

            # Parse JSON
            data = json.loads(decrypted.decode('utf-8'))

            # Validate version
            if data.get('version') != SCHEMA_VERSION:
                logger.warning(f"[CREDENTIALS] Unknown schema version: {data.get('version')}")

            # Convert to CredentialEntry objects
            self._cache = {}
            for cred_id, cred_data in data.get('credentials', {}).items():
                self._cache[cred_id] = CredentialEntry(
                    value=cred_data.get('value', ''),
                    credential_type=cred_data.get('credential_type', 'api_key'),
                    updated_at=cred_data.get('updated_at', ''),
                    updated_by=cred_data.get('updated_by', 'admin')
                )

            logger.info(f"[CREDENTIALS] Loaded {len(self._cache)} credentials from encrypted storage")
            return self._cache

        except Exception as e:
            logger.error(f"[CREDENTIALS] Failed to load credentials: {e}")
            self._cache = {}
            return self._cache

    def _save_all(self, credentials: Dict[str, CredentialEntry]) -> bool:
        """
        Encrypt and save all credentials to file.

        Uses atomic write (temp file + rename) for safety.

        Args:
            credentials: Dict of credential_id -> CredentialEntry

        Returns:
            True if successful
        """
        try:
            # Build data structure
            data = {
                'version': SCHEMA_VERSION,
                'credentials': {
                    cred_id: asdict(entry)
                    for cred_id, entry in credentials.items()
                }
            }

            # Serialize to JSON
            json_bytes = json.dumps(data, indent=2).encode('utf-8')

            # Encrypt
            encrypted = self._encrypt(json_bytes)

            # Atomic write: temp file + rename
            dir_path = self._credentials_path.parent
            with tempfile.NamedTemporaryFile(
                mode='wb',
                dir=dir_path,
                delete=False,
                prefix='cred_',
                suffix='.tmp'
            ) as f:
                f.write(encrypted)
                temp_path = Path(f.name)

            # Rename atomically
            temp_path.replace(self._credentials_path)

            # Update cache
            self._cache = credentials

            logger.info(f"[CREDENTIALS] Saved {len(credentials)} credentials to encrypted storage")
            return True

        except Exception as e:
            logger.error(f"[CREDENTIALS] Failed to save credentials: {e}")
            # Clean up temp file if it exists
            if 'temp_path' in locals() and temp_path.exists():
                temp_path.unlink()
            return False

    def save_credential(
        self,
        credential_id: str,
        value: str,
        credential_type: str = "api_key"
    ) -> bool:
        """
        Save a single credential.

        Args:
            credential_id: Unique identifier (e.g., "openai_api_key")
            value: The credential value
            credential_type: Type of credential ("api_key" or "service_account_json")

        Returns:
            True if successful
        """
        if not self._encryption_available:
            logger.error("[CREDENTIALS] Cannot save: cryptography package not installed")
            return False

        # Load existing
        credentials = self._load_all()

        # Add/update
        credentials[credential_id] = CredentialEntry(
            value=value,
            credential_type=credential_type
        )

        # Save
        return self._save_all(credentials)

    def load_credential(self, credential_id: str) -> Optional[str]:
        """
        Load a single credential value.

        Args:
            credential_id: Unique identifier

        Returns:
            Credential value or None if not found
        """
        credentials = self._load_all()
        entry = credentials.get(credential_id)
        return entry.value if entry else None

    def delete_credential(self, credential_id: str) -> bool:
        """
        Delete a credential.

        Args:
            credential_id: Unique identifier

        Returns:
            True if deleted, False if not found
        """
        credentials = self._load_all()
        if credential_id not in credentials:
            return False

        del credentials[credential_id]
        return self._save_all(credentials)

    def get_credential_status(self, credential_id: str) -> Dict[str, Any]:
        """
        Get credential status without exposing value.

        Args:
            credential_id: Unique identifier

        Returns:
            Status dict with is_configured, updated_at, credential_type
        """
        credentials = self._load_all()
        entry = credentials.get(credential_id)

        if not entry:
            return {
                'is_configured': False,
                'storage_type': 'encrypted_file',
                'updated_at': None,
                'credential_type': None
            }

        return {
            'is_configured': True,
            'storage_type': 'encrypted_file',
            'updated_at': entry.updated_at,
            'credential_type': entry.credential_type
        }

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all credentials.

        Returns:
            Dict of credential_id -> status dict
        """
        credentials = self._load_all()
        return {
            cred_id: {
                'is_configured': True,
                'storage_type': 'encrypted_file',
                'updated_at': entry.updated_at,
                'credential_type': entry.credential_type
            }
            for cred_id, entry in credentials.items()
        }

    def apply_to_environment(self) -> int:
        """
        Load all credentials into os.environ.

        Maps credential IDs to environment variable names:
        - openai_api_key -> OPENAI_API_KEY
        - google_cloud_credentials -> GOOGLE_APPLICATION_CREDENTIALS (writes to temp file)

        Returns:
            Number of credentials applied
        """
        credentials = self._load_all()
        applied = 0

        for cred_id, entry in credentials.items():
            try:
                if cred_id == 'openai_api_key':
                    os.environ['OPENAI_API_KEY'] = entry.value
                    logger.info("[CREDENTIALS] Applied OPENAI_API_KEY from encrypted storage")
                    applied += 1

                elif cred_id == 'google_cloud_credentials':
                    # For Google Cloud, we need to write the JSON to a temp file
                    # and set GOOGLE_APPLICATION_CREDENTIALS to that path
                    if entry.credential_type == 'service_account_json':
                        # Write to a secure temp file in data directory
                        sa_path = self._base_dir / 'data' / '.google_sa_temp.json'
                        sa_path.parent.mkdir(parents=True, exist_ok=True)

                        # Parse and re-serialize to validate JSON
                        sa_data = json.loads(entry.value) if isinstance(entry.value, str) else entry.value
                        sa_path.write_text(json.dumps(sa_data, indent=2))

                        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(sa_path)
                        logger.info("[CREDENTIALS] Applied GOOGLE_APPLICATION_CREDENTIALS from encrypted storage")
                        applied += 1

            except Exception as e:
                logger.error(f"[CREDENTIALS] Failed to apply {cred_id}: {e}")

        return applied

    def is_available(self) -> bool:
        """Check if encrypted storage is available."""
        return self._encryption_available

    def has_credentials(self) -> bool:
        """Check if any credentials are stored."""
        return len(self._load_all()) > 0


# Singleton instance (initialized in app.py with admin password)
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> Optional[CredentialManager]:
    """Get the singleton credential manager instance."""
    return _credential_manager


def init_credential_manager(admin_password: str, base_dir: Optional[Path] = None) -> CredentialManager:
    """
    Initialize the singleton credential manager.

    Args:
        admin_password: Admin password for key derivation
        base_dir: Base directory for credentials file

    Returns:
        CredentialManager instance
    """
    global _credential_manager
    _credential_manager = CredentialManager(admin_password, base_dir)
    return _credential_manager
