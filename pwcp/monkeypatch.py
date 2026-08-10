import os
import ast
import codeop
import marshal
import builtins
import functools
import linecache
from io import BytesIO
from types import CodeType
from collections.abc import MutableMapping
from builtins import compile, eval, exec
from linecache import getlines
from codeop import Compile, _maybe_compile
from weakref import WeakKeyDictionary
from importlib import _bootstrap_external
from importlib._bootstrap_external import (
    _code_to_timestamp_pyc,
    _validate_timestamp_pyc,
    _code_to_hash_pyc,
    _validate_hash_pyc,
)

from .preprocessor import maybe_preprocess, preprocessed_files
from .config import HOOKS
from .hooks import PycType
from .utils import py_from_ppy_filename


pyc_data: MutableMapping[CodeType, dict] = WeakKeyDictionary()

BYTECODE_HEADER_LENGTH = 16
BYTECODE_SIZE_LENGTH = 4


@functools.wraps(getlines)
def patched_getlines(filename, module_globals=None):
    if filename is None:
        return []

    filename = os.path.abspath(filename)
    if filename in preprocessed_files:
        content = preprocessed_files[filename]
        if content is None:
            # preprocessing failed, show original code
            return getlines(filename, module_globals)
        return content.splitlines()

    if PPyLoader.save_files:
        py_filename = py_from_ppy_filename(filename)
        if os.path.isfile(py_filename):
            return getlines(py_filename, module_globals)

    return getlines(filename, module_globals)


@functools.wraps(compile)
def patched_compile(src, filename, *args, **kwargs):
    src = maybe_preprocess(src, filename, {})
    return compile(src, filename, *args, **kwargs)


@functools.wraps(eval)
def patched_eval(src, *args):
    src = maybe_preprocess(src, "<string>", {})
    return eval(src, *args)


@functools.wraps(exec)
def patched_exec(src, *args, **kwargs):
    src = maybe_preprocess(src, "<string>", {})
    return exec(src, *args, **kwargs)


@functools.wraps(_maybe_compile)
def patched_maybe_compile(compiler, src, filename, *args, **kwargs):
    try:
        src = maybe_preprocess(
            src, filename, getattr(compiler, "pwcp_data", {})
        )
    except SyntaxError as e:
        if e.msg and e.msg.startswith("Unterminated"):
            return None
        if len(e.args) < 2 or not e.lineno:
            raise
        msg, eargs, *other = e.args
        eargs = list(eargs)
        eargs[3] = src.splitlines()[e.lineno - 1]
        e.args = (msg, tuple(eargs), *other)
        raise
    try:
        return _maybe_compile(compiler, src, filename, *args, **kwargs)
    except SyntaxError as e:
        if e.msg.startswith(
            ("unexpected EOF while parsing", "expected an indented block")
        ):
            return None
        raise


@functools.wraps(Compile, updated=())
class patched_Compile(Compile):
    def __init__(self):
        super().__init__()
        self.pwcp_data = {}

    def __call__(self, source, filename, symbol, **kwargs):
        source = maybe_preprocess(source, filename, self.pwcp_data)
        return super().__call__(source, filename, symbol, **kwargs)


def _to_pyc(pyc: dict, pyc_type: PycType) -> bytes:
    for hook in HOOKS:
        pyc[hook.name] = hook.create_pyc_data(pyc[hook.name], pyc_type)
    return marshal.dumps(pyc)


def _validate_pyc(pyc: dict, pyc_type: PycType) -> bool:
    for hook in HOOKS:
        pyc_data = pyc.pop(hook.name, None)
        if pyc_data is None:
            return False
        if not hook.validate_pyc_data(pyc_data, pyc_type):
            return False
    # empty = all hooks validated
    return not pyc


@functools.wraps(_code_to_timestamp_pyc)
def patched_code_to_timestamp_pyc(code, mtime=0, source_size=0):
    data = _code_to_timestamp_pyc(code, mtime, source_size)
    if (pyc := pyc_data.pop(code, None)) is not None:
        data.extend(_to_pyc(pyc, PycType.TIMESTAMP_BASED))
    return data


@functools.wraps(_validate_timestamp_pyc)
def patched_validate_timestamp_pyc(
    data, source_mtime, source_size, name, exc_details
):
    _validate_timestamp_pyc(data, source_mtime, source_size, name, exc_details)

    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    # skip code
    marshal.load(data_f)
    try:
        pyc = marshal.load(data_f)
    except Exception:
        return
    if not _validate_pyc(pyc, PycType.TIMESTAMP_BASED):
        raise ImportError(f"bytecode is stale for {name!r}", **exc_details)


@functools.wraps(_code_to_hash_pyc)
def patched_code_to_hash_pyc(code, source_hash, checked=True):
    data = _code_to_hash_pyc(code, source_hash, checked)
    if (pyc := pyc_data.pop(code, None)) is not None:
        data.extend(_to_pyc(pyc, PycType.HASH_BASED))
    return data


@functools.wraps(_validate_hash_pyc)
def patched_validate_hash_pyc(data, source_hash, name, exc_details):
    _validate_hash_pyc(data, source_hash, name, exc_details)

    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    # skip code
    marshal.load(data_f)
    try:
        pyc = marshal.load(data_f)
    except Exception:
        return
    if not _validate_pyc(pyc, PycType.HASH_BASED):
        raise ImportError(
            f"hash in bytecode doesn't match hash of source {name!r}",
            **exc_details,
        )


def apply_monkeypatch():
    global PPyLoader

    from .importers import PPyLoader

    linecache.getlines = patched_getlines

    # let ast use default compile
    ast.compile = compile

    builtins.compile = patched_compile
    builtins.eval = patched_eval
    builtins.exec = patched_exec
    codeop._maybe_compile = patched_maybe_compile
    codeop.Compile = patched_Compile

    _bootstrap_external._code_to_timestamp_pyc = patched_code_to_timestamp_pyc
    _bootstrap_external._validate_timestamp_pyc = (
        patched_validate_timestamp_pyc
    )
    _bootstrap_external._code_to_hash_pyc = patched_code_to_hash_pyc
    _bootstrap_external._validate_hash_pyc = patched_validate_hash_pyc
