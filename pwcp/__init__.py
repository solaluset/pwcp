__all__ = (
    "main",
    "main_with_params",
    "__version__",
    "install",
    "add_file_extension",
    "add_hook",
    "PreprocessorHooks",
    "PycType",
)

from .runner import main, main_with_params
from .version import __version__
from .importers import install
from .config import add_file_extension, add_hook
from .hooks import PreprocessorHooks, PycType, PWCPHooks

add_hook(PWCPHooks())
