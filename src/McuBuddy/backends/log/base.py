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
    def read_recent(self, line_count: int = 50) -> list[str]:
        raise NotImplementedError
