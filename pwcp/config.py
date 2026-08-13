from __future__ import annotations

from importlib.machinery import SOURCE_SUFFIXES
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hooks import PreprocessorHooks

FILE_EXTENSIONS: dict[str, bool] = {}
HOOKS: list[PreprocessorHooks] = []


def add_file_extension(extension: str, /, *, preprocess: bool = True):
    FILE_EXTENSIONS[extension] = not preprocess


add_hook = HOOKS.append


add_file_extension(".ppy")

_DEFAULT_SUFFIXES = tuple(SOURCE_SUFFIXES)
for ext in _DEFAULT_SUFFIXES:
    add_file_extension(ext, preprocess=False)
