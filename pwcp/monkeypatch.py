import os
import _imp
import codeop
import marshal
import builtins
import functools
import linecache
from io import BytesIO
from builtins import compile
from linecache import getlines
from codeop import Compile, _maybe_compile
from importlib import _bootstrap_external
from importlib._bootstrap_external import (
    _code_to_timestamp_pyc,
    _validate_timestamp_pyc,
    _code_to_hash_pyc,
    _validate_hash_pyc,
)

from .preprocessor import PyPreprocessor, maybe_preprocess
from .config import FILE_EXTENSIONS


preprocessed_files = {}
dependencies = {}

BYTECODE_HEADER_LENGTH = 16
BYTECODE_SIZE_LENGTH = 4


@functools.wraps(getlines)
def patched_getlines(filename, module_globals=None):
    if filename in preprocessed_files:
        return preprocessed_files[filename].splitlines()
    return getlines(filename, module_globals)


@functools.wraps(compile)
def patched_compile(src, filename, *args, **kwargs):
    src = maybe_preprocess(src, filename)
    return compile(src, filename, *args, **kwargs)


@functools.wraps(_maybe_compile)
def patched_maybe_compile(compiler, src, filename, symbol):
    try:
        src = maybe_preprocess(
            src, filename, getattr(compiler, "preprocessor", None)
        )
    except SyntaxError as e:
        msg, eargs = e.args
        if msg.startswith("Unterminated"):
            return None
        eargs = list(eargs)
        eargs[3] = src.splitlines()[e.lineno - 1]
        e.args = (msg, tuple(eargs))
        raise
    try:
        return _maybe_compile(compiler, src, filename, symbol)
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
        self.preprocessor = PyPreprocessor()

    def __call__(self, source, filename, symbol, **kwargs):
        source = maybe_preprocess(source, filename, self.preprocessor)
        return super().__call__(source, filename, symbol, **kwargs)


def _get_max_mtime(files: list) -> int:
    return max(int(os.stat(file).st_mtime) for file in files)


@functools.wraps(_code_to_timestamp_pyc)
def patched_code_to_timestamp_pyc(code, mtime=0, source_size=0):
    data = _code_to_timestamp_pyc(code, mtime, source_size)
    deps = dependencies.get(code, None)
    if deps:
        max_mtime = _get_max_mtime(deps)
        data.extend(
            max_mtime.to_bytes(BYTECODE_SIZE_LENGTH, "little", signed=False)
        )
        data.extend(marshal.dumps(deps))
    return data


@functools.wraps(_validate_timestamp_pyc)
def patched_validate_timestamp_pyc(
    data, source_mtime, source_size, name, exc_details
):
    _validate_timestamp_pyc(data, source_mtime, source_size, name, exc_details)
    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    code = marshal.load(data_f)
    if code.co_filename.endswith(tuple(FILE_EXTENSIONS)):
        pyc_mtime = int.from_bytes(
            data_f.read(BYTECODE_SIZE_LENGTH), "little", signed=False
        )
        max_mtime = _get_max_mtime(marshal.load(data_f))
        if max_mtime > pyc_mtime:
            raise ImportError(f"bytecode is stale for {name!r}", **exc_details)


def _get_file_hash(file):
    with open(file, "rb") as f:
        return _imp.source_hash(
            _bootstrap_external._RAW_MAGIC_NUMBER, f.read()
        )


@functools.wraps(_code_to_hash_pyc)
def patched_code_to_hash_pyc(code, source_hash, checked=True):
    source_hash = _get_file_hash(code.co_filename)
    data = _code_to_hash_pyc(code, source_hash, checked)
    deps = dependencies.get(code, None)
    if deps:
        hashes = {file: _get_file_hash(file) for file in deps}
        data.extend(marshal.dumps(hashes))
    return data


@functools.wraps(_validate_hash_pyc)
def patched_validate_hash_pyc(data, source_hash, name, exc_details):
    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    code = marshal.load(data_f)
    source_hash = _get_file_hash(code.co_filename)
    _validate_hash_pyc(data, source_hash, name, exc_details)
    hashes = marshal.load(data_f)
    for file, hash_ in hashes.items():
        if hash_ != _get_file_hash(file):
            raise ImportError(
                f"hash in bytecode doesn't match hash of source {name!r}",
                **exc_details,
            )


def apply_monkeypatch():
    linecache.getlines = patched_getlines
    builtins.compile = patched_compile
    codeop._maybe_compile = patched_maybe_compile
    codeop.Compile = patched_Compile
    _bootstrap_external._code_to_timestamp_pyc = patched_code_to_timestamp_pyc
    _bootstrap_external._validate_timestamp_pyc = (
        patched_validate_timestamp_pyc
    )
    _bootstrap_external._code_to_hash_pyc = patched_code_to_hash_pyc
    _bootstrap_external._validate_hash_pyc = patched_validate_hash_pyc
