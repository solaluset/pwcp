from io import BytesIO, StringIO
from linecache import getline
from tokenize import detect_encoding
from typing import Any, Optional, TextIO

from pypp import Preprocessor

from .config import HOOKS
from .errors import PreprocessorError


class PyPreprocessor(Preprocessor):
    def __init__(self, *, disabled: Optional[bool]):
        super().__init__(disabled=disabled)
        self.included_files = set()

    def on_error(self, file: str, line: int, msg: str):
        raise PreprocessorError(msg, (file, line, 1, getline(file, line)))

    def on_file_open(
        self, is_system_include: bool, includepath: str
    ) -> TextIO:
        self.included_files.add(includepath)
        return super().on_file_open(is_system_include, includepath)

    def _preprocess(self, source: str, filename: str) -> tuple[str, set[str]]:
        self.parse(source, filename)

        out = StringIO()
        try:
            self.write(out)
        except PreprocessorError:
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

    def preprocess(self, source: str, filename: str) -> tuple[str, set[str]]:
        self.return_code = 0
        macros_backup = self.macros.copy()
        try:
            return self._preprocess(source, filename)
        except Exception:
            self.macros = macros_backup
            raise


preprocessed_files: dict[str, str] = {}


def preprocess(src: str, filename: str, data: dict) -> tuple[str, dict]:
    # indicate that we started preprocessing
    preprocessed_files[filename] = None

    result_data = {}
    for hook in HOOKS:
        if hook.name not in data:
            data[hook.name] = hook.create_state()
        src, hook_data = hook.process_source(src, filename, data[hook.name])
        result_data[hook.name] = hook_data

    # save preprocessed file to display actual SyntaxError
    preprocessed_files[filename] = src

    return src, result_data


def maybe_preprocess(src: Any, filename: str, data: dict) -> str:
    if isinstance(src, bytes):
        encoding, _ = detect_encoding(BytesIO(src).readline)
        src = src.decode(encoding)
    if isinstance(src, str):
        # this is essential for interactive mode
        has_newline = src.endswith("\n")
        src, _ = preprocess(src, filename, data)
        if not has_newline:
            src = src.rstrip("\n")
    return src
