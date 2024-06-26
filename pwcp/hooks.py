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
from .preprocessor import preprocess_file
from .utils import import_module_copy, create_sys_clone
from .monkeypatch import (
    apply_monkeypatch,
    dependencies,
    preprocessed_files,
)


# very hacky way to replace `sys` in the PathFinder with our own module
# this is done because we need separate `path_hooks` and `path_importer_cache`
original_pathfinder_module = inspect.getmodule(_PathFinder)
pathfinder_module = import_module_copy(original_pathfinder_module.__name__)
PathFinder = pathfinder_module.PathFinder
vars(pathfinder_module).update(vars(original_pathfinder_module))
pathfinder_module.sys = create_sys_clone()


class Configurable:
    _config = {}

    @classmethod
    def get_config(self) -> dict:
        return self._config

    @classmethod
    def set_config(cls, config: dict):
        cls._config = config


class PPyPathFinder(PathFinder, Configurable):
    """
    An overridden PathFinder which will hunt for ppy files in sys.path
    """

    @classmethod
    def find_spec(
        cls, fullname: str, path: Optional[list] = None, target=None
    ):
        if cls._config.get("prefer_python"):
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


class PPyLoader(SourceFileLoader, Configurable):
    _skip_next_get_data = False
    _get_code_lock = Lock()

    def get_data(self, filename: str) -> Optional[bytes]:
        if self._skip_next_get_data:
            self.__class__._skip_next_get_data = False
            return None

        if filename.endswith(tuple(BYTECODE_SUFFIXES)):
            with open(filename, "rb") as f:
                return f.read()

        # indicate that we started preprocessing
        preprocessed_files[self.path] = None
        data, deps = preprocess_file(self.path, self._config)
        # save preprocessed file to display actual SyntaxError
        preprocessed_files[self.path] = data
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


def _install() -> Callable[[dict], None]:
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
