# Thanks to
# https://stackoverflow.com/a/43573798/
# https://stackoverflow.com/a/45168493/
# https://stackoverflow.com/a/48671982/

import sys
import inspect
from types import CodeType
from threading import Lock
from typing import Callable, Optional
from importlib import invalidate_caches
from importlib.util import find_spec
from importlib.machinery import (
    BYTECODE_SUFFIXES,
    SOURCE_SUFFIXES,
    FileFinder,
    PathFinder as _PathFinder,
    SourceFileLoader,
)

from .config import FILE_EXTENSIONS
from .preprocessor import PyPreprocessor, preprocess_file
from .utils import import_module_copy, create_sys_clone
from .monkeypatch import (
    apply_monkeypatch,
    dependencies,
)


# very hacky way to replace `sys` in the PathFinder with our own module
# this is done because we need separate `path_hooks` and `path_importer_cache`
original_pathfinder_module = inspect.getmodule(_PathFinder)
pathfinder_module = import_module_copy(original_pathfinder_module.__name__)
PathFinder = pathfinder_module.PathFinder
vars(pathfinder_module).update(vars(original_pathfinder_module))
pathfinder_module.sys = create_sys_clone()


class PPyPathFinder(PathFinder):
    """
    An overridden PathFinder which will hunt for ppy files in sys.path
    """

    prefer_python = False

    @classmethod
    def find_spec(
        cls, fullname: str, path: Optional[list] = None, target=None
    ):
        if cls.prefer_python:
            index = sys.meta_path.index(cls)
            del sys.meta_path[index]
            try:
                spec = find_spec(fullname)
            finally:
                sys.meta_path.insert(index, cls)
            if spec:
                return spec

        spec = super().find_spec(fullname, path, target)
        if spec is not None and spec.loader is not None:
            return spec
        return None


class PPyLoader(SourceFileLoader):
    save_files = False
    _skip_next_get_data = False
    _get_code_lock = Lock()

    def get_data(self, filename: str) -> Optional[bytes]:
        if self._skip_next_get_data:
            self.__class__._skip_next_get_data = False
            return None

        if filename.endswith(tuple(BYTECODE_SUFFIXES)):
            with open(filename, "rb") as f:
                return f.read()

        data, deps = preprocess_file(self.path, self.save_files)
        dependencies[self.path] = deps

        return data.encode()

    def source_to_code(self, data: bytes, path: str) -> CodeType:
        code = super().source_to_code(data, path)
        if self.path in dependencies:
            dependencies[code] = dependencies.pop(self.path)
        return code

    def get_code(self, fullname: str) -> CodeType:
        with self._get_code_lock:
            return super().get_code(fullname)


LOADER_DETAILS = PPyLoader, FILE_EXTENSIONS


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
        PPyPathFinder.prefer_python = prefer_python
        PyPreprocessor.default_disabled = not preprocess_unknown_sources

        if done:
            return

        # insert the path finder
        sys.meta_path.insert(0, PPyPathFinder)
        pathfinder_module.sys.path_hooks.append(
            FileFinder.path_hook(LOADER_DETAILS)
        )
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
