from __future__ import annotations

from abc import ABC, abstractmethod


class LogBackend(ABC):
    @abstractmethod
    def connect(self, port: str, baudrate: int = 115200) -> dict:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def write(self, data: bytes) -> int:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(
        self,
        *,
        max_bytes: int,
        timeout_ms: int,
        idle_timeout_ms: int,
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    def read_recent(self, line_count: int = 50) -> list[str]:
        raise NotImplementedError
