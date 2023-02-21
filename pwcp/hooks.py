# Thanks to
# https://stackoverflow.com/a/43573798/
# https://stackoverflow.com/a/45168493/
# https://stackoverflow.com/a/48671982/

import os
import sys
import codeop
import warnings
import builtins
import functools
import linecache
from os import getcwd
from builtins import compile
from linecache import getlines
from codeop import Compile, _maybe_compile
from importlib import invalidate_caches
from importlib.abc import SourceLoader
from importlib.util import spec_from_loader
from importlib.machinery import SOURCE_SUFFIXES, FileFinder, PathFinder, all_suffixes
from traceback import print_exception
from types import ModuleType, TracebackType
from typing import Optional, Type
from .preprocessor import PyPreprocessor, preprocess_file, maybe_preprocess
from .config import FILE_EXTENSION


_path_importer_cache = {}
_path_hooks = []

preprocessed_files = {}


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
        if e.msg == "unexpected EOF while parsing":
            return None
        raise


class patched_Compile(Compile):
    def __init__(self):
        super().__init__()
        self.preprocessor = PyPreprocessor()

    def __call__(self, source, filename, symbol):
        source = maybe_preprocess(source, filename, self.preprocessor)
        return super().__call__(source, filename, symbol)


def apply_monkeypatch():
    linecache.getlines = patched_getlines
    builtins.compile = patched_compile
    codeop._maybe_compile = patched_maybe_compile
    codeop.Compile = patched_Compile


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


class PPyLoader(SourceLoader, Configurable):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, filename):
        """exec_module is already defined for us, we just have to provide a way
        of getting the source code of the module"""
        # save preprocessed file to display actual SyntaxError
        data = preprocessed_files[self.path] = preprocess_file(self.path, self._config)
        return data.encode()


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


LOADER_DETAILS = PPyLoader, [FILE_EXTENSION]


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
        SOURCE_SUFFIXES.append(FILE_EXTENSION)
        # clear any loaders that might already be in use by the FileFinder
        sys.path_importer_cache.clear()
        invalidate_caches()
        # patch standard library
        apply_monkeypatch()

        done = True

    return install


install = _install()
