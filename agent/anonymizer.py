"""PII Anonymization Layer for LLM payloads."""

import logging
import string

logger = logging.getLogger(__name__)


class Anonymizer:
    """
    Replaces real display_name values with tokens before LLM call.
    De-anonymizes LLM response after.

    Token format: USER_A, USER_B, USER_C ... USER_Z, USER_AA, USER_AB ...
    """

    def __init__(self):
        self._real_to_token: dict[str, str] = {}
        self._token_to_real: dict[str, str] = {}
        self._counter = 0

    def _next_token(self) -> str:
        """Generate the next sequential USER token."""
        letters = string.ascii_uppercase
        n = self._counter
        self._counter += 1
        token = ""
        while True:
            token = letters[n % 26] + token
            n = n // 26 - 1
            if n < 0:
                break
        return f"USER_{token}"

    def anonymize_value(self, name: str) -> str:
        """Get or create a token for a display_name."""
        if not name or name in ("Unknown", ""):
            return name
        if name not in self._real_to_token:
            token = self._next_token()
            self._real_to_token[name] = token
            self._token_to_real[token] = name
        return self._real_to_token[name]

    def anonymize_data(self, data: dict, keys_to_anonymize: set[str] | None = None) -> dict:
        """Recursively replace selected field values with tokens."""
        keys = keys_to_anonymize if keys_to_anonymize is not None else {"display_name"}
        if isinstance(data, dict):
            return {
                key: self.anonymize_value(value)
                if key in keys and isinstance(value, str)
                else self.anonymize_data(value, keys)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self.anonymize_data(item, keys) for item in data]
        return data

    def deanonymize(self, text: str) -> str:
        """Replace all tokens in an LLM response with real names."""
        for token, real in self._token_to_real.items():
            text = text.replace(token, real)
        return text

    def mapping_summary(self) -> str:
        """Return the token mapping for debug logging."""
        return str(self._real_to_token)
