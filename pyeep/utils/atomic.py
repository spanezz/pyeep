import contextlib
import os
import os.path
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any


@contextlib.contextmanager
def atomic_writer(
    path: Path,
    mode: str = "w+b",
    chmod: int | None = 0o664,
    sync: bool = True,
    use_umask: bool = False,
    **kw: Any,
) -> Iterator[IO[Any]]:
    """
    open/tempfile wrapper to atomically write to a file, by writing its
    contents to a temporary file in the same directory, and renaming it at the
    end of the block if no exception has been raised.

    :arg path: path of the file to create
    :arg mode: passed to mkstemp/open
    :arg chmod: permissions of the resulting file
    :arg sync: if True, call fdatasync before renaming
    :arg use_umask: if True, apply umask to chmod

    All the other arguments are passed to open
    """

    if chmod is not None and use_umask:
        cur_umask = os.umask(0)
        os.umask(cur_umask)
        chmod &= ~cur_umask

    dirname = path.parent
    fd, abspath_str = tempfile.mkstemp(
        dir=dirname, text="b" not in mode, prefix=path.name
    )
    abspath = Path(abspath_str)
    with open(fd, mode, closefd=True, **kw) as outfd:
        try:
            yield outfd
            outfd.flush()
            if sync:
                os.fdatasync(fd)
            if chmod is not None:
                os.fchmod(fd, chmod)
            abspath.rename(path)
        except Exception:
            abspath.unlink()
            raise
