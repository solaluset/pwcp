# Thanks to
# https://stackoverflow.com/a/43573798/
# https://stackoverflow.com/a/45168493/
# https://stackoverflow.com/a/48671982/

import sys
from os import getcwd
from importlib import invalidate_caches
from importlib.abc import SourceLoader
from importlib.machinery import FileFinder, PathFinder
from .preprocessor import preprocess


_finder_cache = {}
_path_importer_cache = {}
_path_hooks = []


def find_spec_fallback(fullname, path, target):
    if not sys.path_hooks:
        return None

    last = len(sys.path_hooks) - 1

    for idx, hook in enumerate(sys.path_hooks):
        finder = None
        try:
            if hook in _finder_cache:
                finder = _finder_cache[hook]
                if finder is None:
                    # We've tried this finder before and got an ImportError
                    continue
        except TypeError:
            # The hook is unhashable
            pass

        if finder is None:
            try:
                if isinstance(path, list):
                    path = path[0]
                finder = hook(path)
            except ImportError:
                pass

        try:
            _finder_cache[hook] = finder
        except TypeError:
            # The hook is unhashable for some reason so we don't bother
            # caching it
            pass

        if finder is not None:
            spec = finder.find_spec(fullname, target)
            if (spec is not None and
                    (spec.loader is not None or idx == last)):
                # If no __init__.<suffix> was found by any Finder,
                # we may be importing a namespace package (which
                # FileFinder.find_spec returns in this case).  But we
                # only want to return the namespace ModuleSpec if we've
                # exhausted every other finder first.
                return spec

    # Module spec not found through any of the finders
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
            if hasattr(finder, 'invalidate_caches'):
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
        if path == '':
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
        if cls._config.get('prefer_python'):
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
        return preprocess(self.path, self._config)


loader_details = PPyLoader, [".ppy"]


def _install():
    done = False

    def install(config: dict = {}):
        nonlocal done
        if done:
            return
        # setting global configuration
        PPyLoader.set_config(config)
        PPyPathFinder.set_config(config)
        # insert the path finder
        sys.meta_path.insert(0, PPyPathFinder)
        _path_hooks.append(FileFinder.path_hook(loader_details))
        # clear any loaders that might already be in use by the FileFinder
        sys.path_importer_cache.clear()
        invalidate_caches()
        done = True

    return install


install = _install()
