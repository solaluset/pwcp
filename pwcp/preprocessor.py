from io import StringIO
from linecache import getline
from importlib.machinery import SOURCE_SUFFIXES
from typing import Any, Callable, Optional, TextIO, Tuple, Union

from pypp import Preprocessor

from .config import FILE_EXTENSIONS
from .utils import py_from_ppy_filename
from .errors import PreprocessorError


preprocessed_files = {}


class PyPreprocessor(Preprocessor):
    default_disabled = True

    def __init__(self, disabled: Optional[bool] = None):
        if disabled is None:
            disabled = self.default_disabled
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


PreprocessingFunction = Callable[[str, str, PyPreprocessor], str]


def _preprocess(src: str, filename: str, preprocessor: PyPreprocessor) -> str:
    preprocessor.parse(src, filename)

    out = StringIO()
    try:
        preprocessor.write(out)
    except SyntaxError:
        raise
    except Exception as e:
        msg = "internal preprocessor error"
        last = preprocessor.lastdirective
        if last:
            msg += f" at around {last.source}:{last.lineno}"
        raise PreprocessorError(msg) from e

    if preprocessor.return_code != 0:
        raise PreprocessorError(
            f"preprocessor exit code is not zero: {preprocessor.return_code}"
        )

    return out.getvalue()


def set_preprocessing_function(
    func: PreprocessingFunction,
) -> PreprocessingFunction:
    global _preprocess

    prev_func = _preprocess
    _preprocess = func

    return prev_func


def preprocess(
    src: Union[str, TextIO], filename: str, p: Optional[PyPreprocessor] = None
):
    if not isinstance(src, str):
        src = src.read()

    if p is None:
        # always enable preprocessing of ppy files
        if filename.endswith(tuple(FILE_EXTENSIONS)):
            disabled = False
        # but disable other Python files
        elif filename.endswith(tuple(SOURCE_SUFFIXES)):
            disabled = True
        else:
            disabled = None
        p = PyPreprocessor(disabled=disabled)

    # indicate that we started preprocessing
    preprocessed_files[filename] = None

    # save preprocessed file to display actual SyntaxError
    result = preprocessed_files[filename] = _preprocess(src, filename, p)
    return result, p.included_files


def preprocess_file(
    filename: str, save_files: bool = False
) -> Tuple[str, list]:
    with open(filename) as f:
        res, deps = preprocess(f, filename)
    if save_files:
        with open(py_from_ppy_filename(filename), "w") as f:
            f.write(res)
    return res, deps


def maybe_preprocess(
    src: Any, filename: str, preprocessor: Optional[PyPreprocessor] = None
):
    if isinstance(src, bytes):
        src = src.decode()
    if isinstance(src, str):
        # this is essential for interactive mode
        has_newline = src.endswith("\n")
        src, _ = preprocess(src, filename, preprocessor)
        if not has_newline:
            src = src.rstrip("\n")
    return src
