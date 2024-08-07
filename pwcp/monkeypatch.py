import os
import _imp
from _imp import source_hash
import codeop
import marshal
import builtins
import functools
import linecache
from io import BytesIO
from builtins import compile, eval, exec
from linecache import getlines
from codeop import Compile, _maybe_compile
from importlib import _bootstrap_external
from importlib._bootstrap_external import (
    _classify_pyc,
    _code_to_timestamp_pyc,
    _validate_timestamp_pyc,
    _code_to_hash_pyc,
    _validate_hash_pyc,
)

from .preprocessor import PyPreprocessor, maybe_preprocess, preprocessed_files
from .config import FILE_EXTENSIONS
from .utils import py_from_ppy_filename


dependencies = {}

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
    src = maybe_preprocess(src, filename)
    return compile(src, filename, *args, **kwargs)


@functools.wraps(eval)
def patched_eval(src, *args):
    src = maybe_preprocess(src, "<string>")
    return eval(src, *args)


@functools.wraps(exec)
def patched_exec(src, *args, **kwargs):
    src = maybe_preprocess(src, "<string>")
    return exec(src, *args, **kwargs)


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


@functools.wraps(source_hash)
def patched_source_hash(key, source):
    if source is None:
        return None
    return source_hash(key, source)


@functools.wraps(_classify_pyc)
def patched_classify_pyc(data, name, exc_details):
    flags = _classify_pyc(data, name, exc_details)

    hash_based = flags & 0b1 != 0
    if hash_based:
        check_source = flags & 0b10 != 0
        if _imp.check_hash_based_pycs != "never" and (
            check_source or _imp.check_hash_based_pycs == "always"
        ):
            # set skip flag only when our loader is currently working
            PPyLoader._skip_next_get_data = PPyLoader._get_code_lock.locked()

    return flags


def _get_file_mtime(file: str) -> int:
    return int(os.stat(file).st_mtime)


@functools.wraps(_code_to_timestamp_pyc)
def patched_code_to_timestamp_pyc(code, mtime=0, source_size=0):
    data = _code_to_timestamp_pyc(code, mtime, source_size)
    if code in dependencies:
        deps = dependencies.pop(code)
        mtimes = {file: _get_file_mtime(file) for file in deps}
        data.extend(marshal.dumps(mtimes))
    return data


@functools.wraps(_validate_timestamp_pyc)
def patched_validate_timestamp_pyc(
    data, source_mtime, source_size, name, exc_details
):
    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    code = marshal.load(data_f)
    is_pwcp_pyc = code.co_filename.endswith(tuple(FILE_EXTENSIONS))
    if is_pwcp_pyc:
        source_size = int.from_bytes(
            data[
                BYTECODE_HEADER_LENGTH
                - BYTECODE_SIZE_LENGTH : BYTECODE_HEADER_LENGTH
            ],
            "little",
            signed=False,
        )
    _validate_timestamp_pyc(data, source_mtime, source_size, name, exc_details)
    if is_pwcp_pyc:
        mtimes = marshal.load(data_f)
        for file, mtime in mtimes.items():
            try:
                current_mtime = _get_file_mtime(file)
            except FileNotFoundError:
                continue
            if mtime != current_mtime:
                raise ImportError(
                    f"bytecode is stale for {name!r}", **exc_details
                )


def _get_file_hash(file):
    with open(file, "rb") as f:
        return patched_source_hash(
            _bootstrap_external._RAW_MAGIC_NUMBER, f.read()
        )


@functools.wraps(_code_to_hash_pyc)
def patched_code_to_hash_pyc(code, source_hash, checked=True):
    if code in dependencies:
        source_hash = _get_file_hash(code.co_filename)
    data = _code_to_hash_pyc(code, source_hash, checked)
    if code in dependencies:
        deps = dependencies.pop(code)
        hashes = {file: _get_file_hash(file) for file in deps}
        data.extend(marshal.dumps(hashes))
    return data


@functools.wraps(_validate_hash_pyc)
def patched_validate_hash_pyc(data, source_hash, name, exc_details):
    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    code = marshal.load(data_f)
    is_pwcp_pyc = code.co_filename.endswith(tuple(FILE_EXTENSIONS))
    if is_pwcp_pyc:
        assert source_hash is None
        source_hash = _get_file_hash(code.co_filename)
    _validate_hash_pyc(data, source_hash, name, exc_details)
    if is_pwcp_pyc:
        hashes = marshal.load(data_f)
        for file, hash_ in hashes.items():
            try:
                current_hash = _get_file_hash(file)
            except FileNotFoundError:
                continue
            if hash_ != current_hash:
                raise ImportError(
                    f"hash in bytecode doesn't match hash of source {name!r}",
                    **exc_details,
                )


def apply_monkeypatch():
    global PPyLoader

    from .hooks import PPyLoader

    linecache.getlines = patched_getlines

    builtins.compile = patched_compile
    builtins.eval = patched_eval
    builtins.exec = patched_exec
    codeop._maybe_compile = patched_maybe_compile
    codeop.Compile = patched_Compile

    _imp.source_hash = patched_source_hash
    _bootstrap_external._classify_pyc = patched_classify_pyc
    _bootstrap_external._code_to_timestamp_pyc = patched_code_to_timestamp_pyc
    _bootstrap_external._validate_timestamp_pyc = (
        patched_validate_timestamp_pyc
    )
    _bootstrap_external._code_to_hash_pyc = patched_code_to_hash_pyc
    _bootstrap_external._validate_hash_pyc = patched_validate_hash_pyc
