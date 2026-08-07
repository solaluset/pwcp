from typing import Any
from abc import ABC, abstractmethod
from importlib.machinery import SOURCE_SUFFIXES

from .config import FILE_EXTENSIONS
from .preprocessor import PyPreprocessor


class PreprocessorHooks(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def create_state(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def process(
        self, source: str, filename: str, state: Any
    ) -> tuple[str, Any]:
        raise NotImplementedError


class PWCPHooks(PreprocessorHooks):
    skip_unknown_sources = False

    def __init__(self):
        super().__init__("pwcp")

    def create_state(self) -> PyPreprocessor:
        return PyPreprocessor()

    def process(
        self, source: str, filename: str, preprocessor: PyPreprocessor
    ) -> tuple[str, list[str]]:
        if not filename.endswith(tuple(FILE_EXTENSIONS)):
            if filename.endswith(tuple(SOURCE_SUFFIXES)):
                preprocessor.disabled = True
            else:
                preprocessor.disabled = self.skip_unknown_sources
        return preprocessor.preprocess(source, filename)
