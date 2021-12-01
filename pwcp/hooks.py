import sys
from importlib import invalidate_caches
from importlib.abc import SourceLoader
from importlib.machinery import FileFinder
from .preprocessor import preprocess


class PPyLoader(SourceLoader):
    _config = {}

    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, filename):
        """exec_module is already defined for us, we just have to provide a way
        of getting the source code of the module"""
        return preprocess(self.path, self._config)

    @classmethod
    def set_config(cls, config):
        cls._config = config


loader_details = PPyLoader, [".ppy"]


def install(config={}):
    # setting global configuration
    PPyLoader.set_config(config)
    hook = FileFinder.path_hook(loader_details)
    # insert the path hook as requested
    if config.get('prefer_python'):
        sys.path_hooks.append(hook)
    else:
        sys.path_hooks.insert(0, hook)
    # clear any loaders that might already be in use by the FileFinder
    sys.path_importer_cache.clear()
    invalidate_caches()
