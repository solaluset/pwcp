from __future__ import annotations

import os
import sys
import warnings
from _imp import source_hash
from importlib._bootstrap_external import MAGIC_NUMBER
from importlib.machinery import all_suffixes
from traceback import print_exception
from types import ModuleType, TracebackType
from typing import Callable

from .errors import PreprocessorError
from .preprocessor import preprocessed_files

RAW_MAGIC_NUMBER = int.from_bytes(MAGIC_NUMBER, "little")


def create_exception_handler(module: ModuleType | None) -> Callable:
    def handle_exc(
        e_type: type[BaseException],
        e: BaseException,
        tb: TracebackType | None,
    ):
        if (
            isinstance(e, SyntaxError)
            and e.lineno
            and (data := preprocessed_files.get(e.filename))
        ):
            # replace raw text from file with actual code
            e.text = data.splitlines()[e.lineno - 1]
        # remove outer frames from traceback
        orig_tb = tb
        while (
            tb and module and tb.tb_frame.f_code.co_filename != module.__file__
        ):
            tb = tb.tb_next
        if not tb and not isinstance(e, (SyntaxError, PreprocessorError)):
            tb = orig_tb
            print("Internal error:", file=sys.stderr)
        print_exception(e_type, e, tb)

    return handle_exc


def is_package(module_name: str) -> bool:
    if not module_name:
        return False
    module_name = module_name.replace(".", os.sep)
    path_list = [os.path.join(path, module_name) for path in sys.path]
    for path in path_list:
        for suffix in all_suffixes():
            if os.path.isfile(path + suffix):
                return False
    for path in path_list:
        if os.path.isdir(path):
            return True
    warnings.warn("Module file or directory not found, assuming code module.")
    return False


def py_from_ppy_filename(filename: str) -> str:
    return filename + ".py"


def get_file_size(file: str) -> int:
    return os.stat(file).st_size


def get_file_mtime(file: str) -> int:
    return os.stat(file).st_mtime_ns


def get_file_hash(file: str) -> bytes:
    with open(file, "rb") as f:
        return source_hash(RAW_MAGIC_NUMBER, f.read())
