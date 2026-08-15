"""Connection pooling for production safeguards."""

from uuid import uuid4


class ConnectionPool:
    def __init__(self, min_size: int = 2, max_size: int = 10):
        self.min_size = min_size
        self.max_size = max_size
        self._active: dict[str, str] = {}

    def acquire(self, name: str) -> str:
        conn_id = str(uuid4())
        self._active[conn_id] = name
        return conn_id

    def release(self, conn_id: str) -> None:
        self._active.pop(conn_id, None)

    @property
    def active_count(self) -> int:
        return len(self._active)
