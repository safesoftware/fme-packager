import os
from contextlib import contextmanager
from functools import reduce
from pathlib import Path
from typing import Mapping, Iterable


def pipeline(*functions: callable) -> callable:
    def apply_pipeline(starting_value):
        return reduce(lambda value, func: map(func, value), functions, starting_value)

    return apply_pipeline


@contextmanager
def chdir(path: str | Path) -> None:
    """Change the current working directory to the given path and revert back on exit."""
    old_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)


def keep_attributes(mapping: Mapping, *attributes: str) -> dict:
    attributes = set(attributes)
    return {k: v for k, v in mapping.items() if k in attributes}
