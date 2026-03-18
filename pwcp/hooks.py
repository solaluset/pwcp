# Thanks to
# https://stackoverflow.com/a/43573798/
# https://stackoverflow.com/a/45168493/
# https://stackoverflow.com/a/48671982/

import os
import sys
from types import CodeType
from typing import Callable, Optional
from importlib import invalidate_caches
from importlib.machinery import (
    BYTECODE_SUFFIXES,
    SOURCE_SUFFIXES,
    FileFinder,
    PathFinder,
    SourceFileLoader,
)

from .config import FILE_EXTENSIONS
from .preprocessor import PyPreprocessor, preprocess, preprocess_file
from .monkeypatch import (
    apply_monkeypatch,
    dependencies,
)


class PPyLoader(SourceFileLoader):
    save_files = False

    def __init__(
        self, fullname: str, path: str, *, command_line: Optional[str] = None
    ) -> None:
        super().__init__(fullname, path)
        self.command_line = command_line

    def get_data(self, filename: str) -> Optional[bytes]:
        if filename == "-c":
            return preprocess(self.command_line, filename)[0].encode()

        if filename.endswith(tuple(BYTECODE_SUFFIXES)):
            with open(filename, "rb") as f:
                return f.read()

        data, deps = preprocess_file(self.path, self.save_files)
        dependencies[self.path] = deps

        return data.encode()

    def source_to_code(self, data: bytes, path: str, *args) -> CodeType:
        code = super().source_to_code(data, path, *args)
        if self.path in dependencies:
            dependencies[code] = dependencies.pop(self.path)
        return code


LOADER_DETAILS = PPyLoader, FILE_EXTENSIONS


class PPyPathFinder(PathFinder):
    """
    An overridden PathFinder which will hunt for ppy files in sys.path
    """

    hook = FileFinder.path_hook(LOADER_DETAILS)
    cache = {}

    @classmethod
    def invalidate_caches(cls):
        super().invalidate_caches()
        cls.cache.clear()

    @classmethod
    def _path_hooks(cls, path):
        try:
            return cls.hook(path)
        except ImportError:
            return None

    @classmethod
    def _path_importer_cache(cls, path):
        if path == "":
            try:
                path = os.getcwd()
            except FileNotFoundError:
                return None
        try:
            finder = cls.cache[path]
        except KeyError:
            finder = cls.cache[path] = cls._path_hooks(path)
        return finder

    @classmethod
    def find_spec(
        cls, fullname: str, path: Optional[list] = None, target=None
    ):
        spec = super().find_spec(fullname, path, target)
        if spec is not None and spec.loader is not None:
            return spec
        return None


def _install() -> Callable[..., None]:
    done = False

    def install(
        *,
        save_files: bool,
        prefer_python: bool,
        preprocess_unknown_sources: bool,
    ):
        nonlocal done

        # (re)setting global configuration
        PPyLoader.save_files = save_files
        PyPreprocessor.default_disabled = not preprocess_unknown_sources

        # insert the path finder
        try:
            sys.meta_path.remove(PPyPathFinder)
        except ValueError:
            pass
        if prefer_python:
            sys.meta_path.append(PPyPathFinder)
        else:
            sys.meta_path.insert(0, PPyPathFinder)

        if done:
            return

        # register our extension
        SOURCE_SUFFIXES.extend(FILE_EXTENSIONS)
        # clear any loaders that might already be in use by the FileFinder
        invalidate_caches()
        # patch standard library
        apply_monkeypatch()

        done = True

    return install


install = _install()
