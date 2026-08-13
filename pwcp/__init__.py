__all__ = (
    "PreprocessorHooks",
    "PycType",
    "__version__",
    "add_file_extension",
    "add_hook",
    "install",
    "main",
    "main_with_params",
    "preprocess",
)

from .config import add_file_extension, add_hook
from .hooks import PreprocessorHooks, PWCPHooks, PycType
from .importers import install
from .preprocessor import preprocess
from .runner import main, main_with_params
from .version import __version__

add_hook(PWCPHooks())
