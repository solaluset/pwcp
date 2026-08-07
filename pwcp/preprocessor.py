from io import StringIO
from linecache import getline
from typing import TextIO

from pypp import Preprocessor

from .errors import PreprocessorError


class PyPreprocessor(Preprocessor):
    def __init__(self):
        super().__init__()
        self.included_files = []

    def write(self, file: TextIO):
        macros_backup = self.macros.copy()
        try:
            super().write(file)
        except Exception:
            self.macros = macros_backup
            raise

    def on_error(self, file: str, line: int, msg: str):
        raise SyntaxError(msg, (file, line, 1, getline(file, line)))

    def on_file_open(
        self, is_system_include: bool, includepath: str
    ) -> TextIO:
        self.included_files.append(includepath)
        return super().on_file_open(is_system_include, includepath)

    def preprocess(self, source: str, filename: str) -> tuple[str, list[str]]:
        self.parse(source, filename)

        out = StringIO()
        try:
            self.write(out)
        except SyntaxError:
            raise
        except Exception as e:
            msg = "internal preprocessor error"
            last = self.lastdirective
            if last:
                msg += f" at around {last.source}:{last.lineno}"
            raise PreprocessorError(msg) from e

        if self.return_code != 0:
            raise PreprocessorError(
                f"preprocessor exit code is not zero: {self.return_code}"
            )

        return out.getvalue(), self.included_files
