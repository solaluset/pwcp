# Thanks to
# https://stackoverflow.com/a/43573798/
# https://stackoverflow.com/a/45168493/
# https://stackoverflow.com/a/48671982/

import sys
from os import getcwd
from importlib import invalidate_caches
from importlib import _bootstrap_external
from importlib.util import spec_from_loader
from importlib.machinery import (
    BYTECODE_SUFFIXES,
    SOURCE_SUFFIXES,
    FileFinder,
    PathFinder,
    SourceFileLoader,
)

from .config import FILE_EXTENSIONS
from .preprocessor import preprocess_file
from .monkeypatch import (
    BYTECODE_HEADER_LENGTH,
    BYTECODE_SIZE_LENGTH,
    apply_monkeypatch,
    dependencies,
    preprocessed_files,
)


_path_importer_cache = {}
_path_hooks = []


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
    _skip_next_get_data = False
    _in_get_code = False

    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, filename):
        if self._skip_next_get_data:
            self.__class__._skip_next_get_data = False
            return None

        if filename.endswith(tuple(BYTECODE_SUFFIXES)):
            with open(filename, "rb") as f:
                # replace size because it will never match after preprocessing
                data = f.read(BYTECODE_HEADER_LENGTH)
                flags = _bootstrap_external._classify_pyc(data, filename, {})
                hash_based = flags & 0b1 != 0
                if not hash_based:
                    data = data[:-BYTECODE_SIZE_LENGTH] + self.path_stats(
                        self.path
                    )["size"].to_bytes(
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

    def get_code(self, fullname):
        self.__class__._in_get_code = True
        try:
            return super().get_code(fullname)
        finally:
            self.__class__._in_get_code = False


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
