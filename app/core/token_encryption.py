import os

from cryptography.fernet import Fernet, InvalidToken


class TokenEncryptionError(ValueError):
    pass


class TokenCipher:
    def __init__(self):
        key = os.environ.get("SPOTIFY_TOKEN_ENCRYPTION_KEY", "").strip()
        self._fernet = None
        self._configuration_error = None
        if key:
            try:
                self._fernet = Fernet(key.encode("utf-8"))
            except (TypeError, ValueError):
                self._configuration_error = (
                    "SPOTIFY_TOKEN_ENCRYPTION_KEY must be a valid Fernet key"
                )

    @property
    def configured(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str) -> str:
        if self._fernet is None:
            raise TokenEncryptionError(
                self._configuration_error
                or "Spotify token encryption is not configured"
            )
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        if self._fernet is None:
            raise TokenEncryptionError(
                self._configuration_error
                or "Spotify token encryption is not configured"
            )
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as error:
            raise TokenEncryptionError("Stored Spotify token cannot be decrypted") from error
