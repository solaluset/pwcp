# Thanks to
# https://stackoverflow.com/a/43573798/
# https://stackoverflow.com/a/45168493/
# https://stackoverflow.com/a/48671982/

import os
import sys
import _imp
import codeop
import marshal
import warnings
import builtins
import functools
import linecache
from os import getcwd
from io import BytesIO
from builtins import compile
from linecache import getlines
from codeop import Compile, _maybe_compile
from importlib import invalidate_caches
from importlib import _bootstrap_external
from importlib.util import spec_from_loader
from importlib.machinery import BYTECODE_SUFFIXES, SOURCE_SUFFIXES, FileFinder, PathFinder, SourceFileLoader, all_suffixes
from importlib._bootstrap_external import _code_to_timestamp_pyc, _validate_timestamp_pyc, _code_to_hash_pyc, _validate_hash_pyc
from traceback import print_exception
from types import ModuleType, TracebackType
from typing import Optional, Type
from .preprocessor import PyPreprocessor, preprocess_file, maybe_preprocess
from .config import FILE_EXTENSIONS


_path_importer_cache = {}
_path_hooks = []

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
        src = maybe_preprocess(src, filename, getattr(compiler, "preprocessor", None))
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
        data.extend(max_mtime.to_bytes(BYTECODE_SIZE_LENGTH, "little", signed=False))
        data.extend(marshal.dumps(deps))
    return data


@functools.wraps(_validate_timestamp_pyc)
def patched_validate_timestamp_pyc(data, source_mtime, source_size, name, exc_details):
    _validate_timestamp_pyc(data, source_mtime, source_size, name, exc_details)
    data_f = BytesIO(data[BYTECODE_HEADER_LENGTH:])
    code = marshal.load(data_f)
    if code.co_filename.endswith(tuple(FILE_EXTENSIONS)):
        pyc_mtime = int.from_bytes(data_f.read(BYTECODE_SIZE_LENGTH), "little", signed=False)
        max_mtime = _get_max_mtime(marshal.load(data_f))
        if max_mtime > pyc_mtime:
            raise ImportError(f"bytecode is stale for {name!r}", **exc_details)


def _get_file_hash(file):
    with open(file, "rb") as f:
        return _imp.source_hash(_bootstrap_external._RAW_MAGIC_NUMBER, f.read())


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
    _bootstrap_external._validate_timestamp_pyc = patched_validate_timestamp_pyc
    _bootstrap_external._code_to_hash_pyc = patched_code_to_hash_pyc
    _bootstrap_external._validate_hash_pyc = patched_validate_hash_pyc


def find_spec_fallback(fullname, path, target):
    spec = None
    for finder in sys.meta_path:
        if finder == PPyPathFinder:
            continue
        try:
            spec = finder.find_spec(fullname, path, target)
        except AttributeError:
            loader = finder.find_module(fullname, path)
            if loader:
                spec = spec_from_loader(fullname, loader)
        if spec and spec.loader:
            return spec
    return None


class Configurable:
    _config = {}

    @classmethod
    def set_config(cls, config: dict):
        cls._config = config


class PPyPathFinder(PathFinder, Configurable):
    """
    An overridden PathFinder which will hunt for ppy files in
    sys.path. Uses storage in this module to avoid conflicts with the
    original PathFinder
    """

    @classmethod
    def invalidate_caches(cls):
        for finder in _path_importer_cache.values():
            if hasattr(finder, "invalidate_caches"):
                finder.invalidate_caches()

    @classmethod
    def _path_hooks(cls, path):
        for hook in _path_hooks:
            try:
                return hook(path)
            except ImportError:
                continue
        else:
            return None

    @classmethod
    def _path_importer_cache(cls, path):
        if path == "":
            try:
                path = getcwd()
            except FileNotFoundError:
                # Don't cache the failure as the cwd can easily change to
                # a valid directory later on.
                return None
        try:
            finder = _path_importer_cache[path]
        except KeyError:
            finder = cls._path_hooks(path)
            _path_importer_cache[path] = finder
        return finder

    @classmethod
    def find_spec(cls, fullname, path, target=None):
        if cls._config.get("prefer_python"):
            spec = find_spec_fallback(fullname, path, target)
            if spec:
                return spec

        spec = super().find_spec(fullname, path, target)
        if spec is not None and spec.loader is not None:
            return spec
        return None


class PPyLoader(SourceFileLoader, Configurable):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, filename):
        if filename.endswith(tuple(BYTECODE_SUFFIXES)):
            with open(filename, "rb") as f:
                # replace size because it will never match after preprocessing
                data = f.read(BYTECODE_HEADER_LENGTH)
                flags = _bootstrap_external._classify_pyc(data, filename, {})
                hash_based = flags & 0b1 != 0
                if not hash_based:
                    data = data[:-BYTECODE_SIZE_LENGTH] + self.path_stats(self.path)["size"].to_bytes(
                        BYTECODE_SIZE_LENGTH,
                        "little",
                        signed=False,
                    )
                return data + f.read()

        data, deps = preprocess_file(self.path, self._config)
        # save preprocessed file to display actual SyntaxError
        preprocessed_files[self.path] = data
        dependencies[self.path] = deps
        return data.encode()

    def source_to_code(self, data, path):
        code = super().source_to_code(data, path)
        if self.path in dependencies:
            dependencies[code] = dependencies.pop(self.path)
        return code


def create_exception_handler(module: Optional[ModuleType]):
    def handle_exc(
        e_type: Type[BaseException], e: BaseException, tb: Optional[TracebackType]
    ):
        if isinstance(e, SyntaxError) and preprocessed_files.get(e.filename):
            # replace raw text from file with actual code
            data = preprocessed_files[e.filename]
            e.text = data.splitlines()[e.lineno - 1]
        # remove outer frames from traceback
        while tb and module and tb.tb_frame.f_code.co_filename != module.__file__:
            tb = tb.tb_next
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


LOADER_DETAILS = PPyLoader, FILE_EXTENSIONS


def _install():
    done = False

    def install(config: dict = {}):
        nonlocal done

        # (re)setting global configuration
        PPyLoader.set_config(config)
        PPyPathFinder.set_config(config)

        if done:
            return

        # insert the path finder
        sys.meta_path.insert(0, PPyPathFinder)
        _path_hooks.append(FileFinder.path_hook(LOADER_DETAILS))
        # register our extension
        SOURCE_SUFFIXES.extend(FILE_EXTENSIONS)
        # clear any loaders that might already be in use by the FileFinder
        sys.path_importer_cache.clear()
        invalidate_caches()
        # patch standard library
        apply_monkeypatch()

        done = True

    return install


install = _install()
