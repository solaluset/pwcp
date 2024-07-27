from io import StringIO
from linecache import getline
from typing import Any, Optional, TextIO, Tuple, Union

from pypp import Preprocessor

from .config import FILE_EXTENSIONS
from .utils import py_from_ppy_filename
from .errors import PreprocessorError


class PyPreprocessor(Preprocessor):
    def __init__(self, disabled=False):
        super().__init__(disabled=disabled)
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


def preprocess(src: Union[str, TextIO], p: Optional[PyPreprocessor] = None):
    if p is None:
        p = PyPreprocessor()
    p.parse(src)
    out = StringIO()
    try:
        p.write(out)
    except SyntaxError:
        raise
    except Exception as e:
        msg = "internal preprocessor error"
        last = p.lastdirective
        if last:
            msg += f" at around {last.source}:{last.lineno}"
        raise PreprocessorError(msg) from e
    if p.return_code != 0:
        raise PreprocessorError("preprocessor exit code is not zero")
    return out.getvalue(), p.included_files


def preprocess_file(filename: str, config: dict = {}) -> Tuple[str, list]:
    with open(filename) as f:
        res, deps = preprocess(f)
    if config.get("save_files"):
        with open(py_from_ppy_filename(filename), "w") as f:
            f.write(res)
    return res, deps


def maybe_preprocess(
    src: Any, filename: str, preprocessor: Optional[PyPreprocessor] = None
):
    if isinstance(src, bytes):
        src = src.decode()
    if isinstance(src, str):
        # disable preprocessing of non-ppy files by default
        if preprocessor is None and not filename.endswith(tuple(FILE_EXTENSIONS)):
            preprocessor = PyPreprocessor(disabled=True)
        # this is essential for interactive mode
        has_newline = src.endswith("\n")
        src, _ = preprocess(src, preprocessor)
        if not has_newline:
            src = src.rstrip("\n")
    return src
