"""PII Anonymization Layer for LLM payloads."""

import logging
import string
import threading
import time
import uuid

logger = logging.getLogger(__name__)
SESSION_TTL = 1800


class Anonymizer:
    """Replaces real display_name values with tokens before LLM calls."""

    def __init__(self):
        self._real_to_token: dict[str, str] = {}
        self._token_to_real: dict[str, str] = {}
        self._counter = 0

    def _next_token(self) -> str:
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
        if not name or name in ("Unknown", ""):
            return name
        if name not in self._real_to_token:
            token = self._next_token()
            self._real_to_token[name] = token
            self._token_to_real[token] = name
        return self._real_to_token[name]

    def anonymize_data(self, data: dict, keys_to_anonymize: set[str] | None = None) -> dict:
        keys = keys_to_anonymize if keys_to_anonymize is not None else {"display_name"}
        if isinstance(data, dict):
            return {key: self.anonymize_value(value) if key in keys and isinstance(value, str) else self.anonymize_data(value, keys) for key, value in data.items()}
        if isinstance(data, list):
            return [self.anonymize_data(item, keys) for item in data]
        return data

    def anonymize_text(self, text: str) -> str:
        if not text:
            return text
        import re
        for real in sorted(self._real_to_token.keys(), key=len, reverse=True):
            if not real:
                continue
            prefix = r"(?<!\w)" if real[0].isalnum() else ""
            suffix = r"(?!\w)" if real[-1].isalnum() else ""
            pattern = re.compile(prefix + re.escape(real) + suffix, re.IGNORECASE)
            text = pattern.sub(self._real_to_token[real], text)
        return text

    def deanonymize(self, text: str) -> str:
        for token, real in self._token_to_real.items():
            text = text.replace(token, real)
        return text

    def mapping_summary(self) -> str:
        return str(self._real_to_token)


class SessionStore:
    def __init__(self):
        self._sessions: dict = {}
        self._lock = threading.Lock()
        self._start_cleanup()

    def create(self) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = {"anonymizer": Anonymizer(), "history": [], "last_active": time.time()}
        logger.info("SessionStore: created session %s", session_id)
        return session_id

    def get(self, session_id: str) -> dict | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session["last_active"] = time.time()
            return session

    def append_history(self, session_id: str, role: str, content: str):
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session["history"].append({"role": role, "content": content})

    def delete(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)

    def _cleanup(self):
        while True:
            time.sleep(300)
            now = time.time()
            with self._lock:
                expired = [sid for sid, session in self._sessions.items() if now - session["last_active"] > SESSION_TTL]
                for sid in expired:
                    del self._sessions[sid]
            if expired:
                logger.info("SessionStore: cleaned up %d expired sessions", len(expired))

    def _start_cleanup(self):
        threading.Thread(target=self._cleanup, daemon=True).start()


session_store = SessionStore()
