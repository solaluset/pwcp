from typing import Any
from enum import Enum, auto
from abc import ABC, abstractmethod
from importlib.machinery import SOURCE_SUFFIXES

from .version import __version__
from .utils import get_file_mtime
from .config import FILE_EXTENSIONS
from .preprocessor import PyPreprocessor


class PycType(Enum):
    TIMESTAMP_BASED = auto()
    HASH_BASED = auto()


class PreprocessorHooks(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def create_state(self) -> Any:
        """
        Create state later passed to `process_source()`
        """
        raise NotImplementedError

    @abstractmethod
    def process_source(
        self, source: str, filename: str, state: Any
    ) -> tuple[str, Any]:
        """
        Apply source code modifications
        `state` is created with `create_state()`
        Must return new source and data for `create_pyc_info()`
        """
        raise NotImplementedError

    @abstractmethod
    def create_pyc_data(self, data: Any, pyc_type: PycType) -> dict:
        """
        Turn `data` into marshallable dict to store in pyc
        """
        raise NotImplementedError

    @abstractmethod
    def validate_pyc_data(self, data: dict, pyc_type: PycType) -> bool:
        """
        Check if pyc data matches
        """
        raise NotImplementedError


class PWCPHooks(PreprocessorHooks):
    skip_unknown_sources = False

    def __init__(self):
        super().__init__("pwcp")

    def create_state(self) -> PyPreprocessor:
        return PyPreprocessor()

    def process_source(
        self, source: str, filename: str, preprocessor: PyPreprocessor
    ) -> tuple[str, list[str]]:
        if not filename.endswith(tuple(FILE_EXTENSIONS)):
            if filename.endswith(tuple(SOURCE_SUFFIXES)):
                preprocessor.disabled = True
            else:
                preprocessor.disabled = self.skip_unknown_sources
        return preprocessor.preprocess(source, filename)

    def create_pyc_data(self, data: list[str], pyc_type: PycType) -> dict:
        result = {"version": __version__}
        if pyc_type == PycType.TIMESTAMP_BASED:
            result["files"] = {file: get_file_mtime(file) for file in data}
        elif pyc_type == PycType.HASH_BASED:
            ...
        else:
            raise ValueError(f"unknown pyc type {pyc_type}")
        return result

    def validate_pyc_data(self, data: dict, pyc_type: PycType) -> bool:
        if data["version"] != __version__:
            return False
        if pyc_type == PycType.TIMESTAMP_BASED:
            for file, mtime in data["files"].items():
                try:
                    current_mtime = get_file_mtime(file)
                except FileNotFoundError:
                    continue
                if mtime != current_mtime:
                    return False
        elif pyc_type == PycType.HASH_BASED:
            ...
        else:
            raise ValueError(f"unknown pyc type {pyc_type}")
        return True
