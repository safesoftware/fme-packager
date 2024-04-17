import os
from contextlib import contextmanager
from pathlib import Path
from typing import Union


@contextmanager
def chdir(path: Union[str, Path]) -> None:
    """Change the current working directory to the given path and revert back on exit."""
    old_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)
