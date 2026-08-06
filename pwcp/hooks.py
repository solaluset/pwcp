from abc import ABC, abstractmethod
from typing import Any

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
    def __init__(self):
        super().__init__("pwcp")

    def create_state(self) -> PyPreprocessor:
        return PyPreprocessor(disabled=False)

    def process(
        self, source: str, filename: str, preprocessor: PyPreprocessor
    ) -> tuple[str, list[str]]:
        preprocessor.disabled = filename.endswith(".py")
        return preprocessor.preprocess(source, filename)
