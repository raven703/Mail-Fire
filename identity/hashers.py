"""Wrap legacy PHC strings; successful login upgrades them to Django Argon2."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash


class LegacyArgon2PasswordHasher(BasePasswordHasher):
    algorithm = "legacy_argon2"

    def encode(self, password, salt):
        return f"{self.algorithm}${PasswordHasher().hash(password)}"

    def verify(self, password, encoded):
        try:
            return PasswordHasher().verify(encoded.split("$", 1)[1], password)
        except (VerificationError, InvalidHashError, ValueError):
            return False

    def safe_summary(self, encoded):
        return {"algorithm": self.algorithm, "hash": mask_hash(encoded)}

    def must_update(self, encoded):
        return True

    def harden_runtime(self, password, encoded):
        pass
