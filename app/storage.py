from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.models import SessionData


class InMemorySessionStore:
    def __init__(self) -> None:
        self._items: dict[str, SessionData] = {}
        self._lock = Lock()

    def create(self, original_resume: str, job_description: str, source_filename: str = "") -> SessionData:
        session = SessionData(
            session_id=str(uuid4()),
            created_at=datetime.utcnow(),
            original_resume=original_resume,
            job_description=job_description,
            source_filename=source_filename,
        )
        with self._lock:
            self._items[session.session_id] = session
        return session

    def get(self, session_id: str) -> Optional[SessionData]:
        with self._lock:
            return self._items.get(session_id)

    def save(self, session: SessionData) -> SessionData:
        with self._lock:
            self._items[session.session_id] = session
        return session
