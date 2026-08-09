"""Buffered NDJSON ``logging.Handler`` for Conclave application frames.

Attach to :data:`~aioafero.v1.conclave.client.FRAME_LOGGER` while Conclave runs;
call :meth:`~logging.Handler.flush` (or :meth:`close`) to harvest. Home Assistant
can do the same and anonymize on Generate Debug later.
"""

from __future__ import annotations

__all__ = [
    "ConclaveFrameFileHandler",
    "attach_frame_capture",
]

import json
import logging
from pathlib import Path
from typing import Any

from .client import FRAME_LOGGER

DEFAULT_BUFFER_SIZE = 32


class ConclaveFrameFileHandler(logging.Handler):
    """Buffer log records in memory and append them to an NDJSON file.

    Each emitted record's formatted message is one JSON object (as produced by
    the Conclave frame logger). When the buffer reaches ``capacity``, or when
    :meth:`flush` / :meth:`close` is called, lines are appended to ``filename``.
    """

    def __init__(
        self,
        filename: str | Path,
        *,
        capacity: int = DEFAULT_BUFFER_SIZE,
        encoding: str = "utf-8",
    ) -> None:
        """Create a handler that writes buffered frame lines to ``filename``."""
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        super().__init__(level=logging.DEBUG)
        self.baseFilename = str(Path(filename))
        self.capacity = capacity
        self.encoding = encoding
        self._buffer: list[str] = []
        self.setFormatter(logging.Formatter("%(message)s"))

    @property
    def path(self) -> Path:
        """Destination NDJSON file."""
        return Path(self.baseFilename)

    @property
    def buffered_count(self) -> int:
        """Frames waiting in memory (not yet flushed)."""
        return len(self._buffer)

    def emit(self, record: logging.LogRecord) -> None:
        """Buffer ``record``; spill to disk when the buffer is full."""
        try:
            self._buffer.append(self.format(record))
            if len(self._buffer) >= self.capacity:
                self.flush()
        except Exception:  # noqa: BLE001 - match logging.Handler.emit contract
            self.handleError(record)

    def flush(self) -> None:
        """Append buffered lines to the capture file and clear the buffer."""
        self.acquire()
        try:
            if not self._buffer:
                return
            path = self.path
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding=self.encoding) as handle:
                for line in self._buffer:
                    handle.write(line)
                    handle.write("\n")
            self._buffer.clear()
        finally:
            self.release()

    def close(self) -> None:
        """Flush remaining frames and close the handler."""
        try:
            self.flush()
        finally:
            super().close()

    def read_frames(self) -> list[dict[str, Any]]:
        """Flush, then load all NDJSON objects from :attr:`path`."""
        self.flush()
        if not self.path.is_file():
            return []
        frames: list[dict[str, Any]] = []
        with self.path.open(encoding=self.encoding) as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                frames.append(json.loads(line))
        return frames


def attach_frame_capture(
    path: str | Path,
    *,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
    propagate: bool = False,
) -> ConclaveFrameFileHandler:
    """Add a :class:`ConclaveFrameFileHandler` to :data:`FRAME_LOGGER`.

    Raises the frame logger to ``DEBUG`` and sets ``propagate``. Caller should
    :meth:`~ConclaveFrameFileHandler.flush` to harvest, then
    ``FRAME_LOGGER.removeHandler(handler)`` and ``handler.close()``.

    :param path: Destination NDJSON file.
    :param buffer_size: Frames held before a disk spill.
    :param propagate: When false (default), frame lines stay off parent loggers.
    """
    handler = ConclaveFrameFileHandler(path, capacity=buffer_size)
    FRAME_LOGGER.setLevel(logging.DEBUG)
    FRAME_LOGGER.propagate = propagate
    FRAME_LOGGER.addHandler(handler)
    return handler
