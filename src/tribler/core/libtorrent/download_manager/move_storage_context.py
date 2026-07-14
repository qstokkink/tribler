from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Future
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType

    import libtorrent as lt

    from tribler.core.libtorrent.download_manager.download_state import DownloadState


logger = logging.getLogger(__name__)


def peek(file_path: Path, offset: int) -> int | None:
    """
    Read a single byte from a given file at the given offset.
    """
    if not file_path.exists():
        return None
    try:
        with open(file_path, "rb", buffering=0) as fp:
            fp.seek(offset, os.SEEK_SET)
            os.set_blocking(fp.fileno(), False)
            b = fp.read(1)
            return b[0] if len(b) else None
    except OSError:
        logger.exception("Failed to peek at offset %d of %s.", offset, str(file_path))
        return None  # A myriad of errors may still occur


def to_move_tuple(storage: lt.file_storage, piece_idx: int, src: Path, dst: Path) -> tuple[int, int, int, int, Path, Path]:
    j = storage.file_index_at_piece(piece_idx)
    offset = (piece_idx - storage.piece_index_at_file(j)) * storage.piece_length()
    file_src = src / storage.file_path(j)

    return (
        j,  # Sort order: first file index.
        piece_idx,  # Sort order: then piece index.
        offset,  # This is not necessarily the first byte in the piece, but shifted with the file start.
        peek(file_src, offset),
        file_src,
        dst / storage.file_path(j),
    )


class MoveContext(AbstractAsyncContextManager):


    def __init__(self, storage: lt.file_storage, status: DownloadState, src: Path, dst: Path,
                 aborter: Future[lt.alert]) -> None:
        super().__init__()

        verified_pieces = status.lt_status.pieces if status.lt_status is not None else []
        self.status = status

        self.remaining: list[tuple[int, int, int, int, Path, Path]] = [
            to_move_tuple(storage, i, src, dst)
            for i in range(len(verified_pieces))
            if verified_pieces[i]
        ]
        self.remaining.sort(reverse=True)  # Uses elements of tuples, in order of appearance. Reverse to pop() lowest.

        self.total = len(self.remaining)
        self._abort = False

        aborter.add_done_callback(self.abort)

    def abort(self, alert: lt.alert | None) -> None:
        self._abort = True

    async def _peek(self, file_path: Path, offset: int) -> int | None:
        return await asyncio.get_running_loop().run_in_executor(None, peek, file_path, offset)

    async def readloop(self) -> None:
        while len(self.remaining) and not self._abort:
            _, __, offset, expected, ___, file_path = self.remaining.pop()
            if expected is None:  # Reading the source failed unexpectedly: ignore.
                continue

            while (await self._peek(file_path, offset)) != expected and not self._abort:
                self.status.move_progress = self.progress()
                await asyncio.sleep(0.1)
            self.status.move_progress = self.progress()

    def progress(self) -> float:
        if self.total == 0:
            return 1.0
        return (self.total - len(self.remaining)) / self.total

    async def __aenter__(self) -> Self:
        return await asyncio.gather(super().__aenter__(), self.readloop())

    async def __aexit__(
            self, exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None, /):
        self.abort(None)
