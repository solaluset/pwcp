from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hooks import PreprocessorHooks

FILE_EXTENSIONS: list[str] = []
HOOKS: list[PreprocessorHooks] = []

add_file_extension = FILE_EXTENSIONS.append
add_hook = HOOKS.append
