import contextvars
from contextlib import contextmanager

verbose_flag = contextvars.ContextVar("verbose", default=False)


@contextmanager
def set_verbose(level):
    token = verbose_flag.set(level)
    try:
        yield
    finally:
        verbose_flag.reset(token)
