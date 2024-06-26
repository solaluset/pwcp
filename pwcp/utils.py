import os
import sys
import warnings
from typing import Callable, Optional, Type
from traceback import print_exception
from types import ModuleType, TracebackType
from importlib import util
from importlib.machinery import all_suffixes

from .errors import PreprocessorError


def create_exception_handler(module: Optional[ModuleType]) -> Callable:
    def handle_exc(
        e_type: Type[BaseException],
        e: BaseException,
        tb: Optional[TracebackType],
    ):
        from .monkeypatch import preprocessed_files

        if isinstance(e, SyntaxError) and preprocessed_files.get(e.filename):
            # replace raw text from file with actual code
            data = preprocessed_files[e.filename]
            e.text = data.splitlines()[e.lineno - 1]
        # remove outer frames from traceback
        orig_tb = tb
        while (
            tb and module and tb.tb_frame.f_code.co_filename != module.__file__
        ):
            tb = tb.tb_next
        if not tb:
            tb = orig_tb
            if not isinstance(e, (SyntaxError, PreprocessorError)):
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
    file_path = os.path.splitext(filename)[0]
    return file_path + ".py"


def import_module_copy(name: str):
    orig_module = sys.modules.pop(name, None)
    spec = util.find_spec(name)
    if orig_module:
        sys.modules[name] = orig_module

    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def create_sys_clone():
    sys_clone = ModuleType("sys")
    vars(sys_clone).update(vars(sys))
    sys_clone.path_hooks = []
    sys_clone.path_importer_cache = {}

    return sys_clone
