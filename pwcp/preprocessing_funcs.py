from typing import Any, TextIO, Tuple, Union

from .config import HOOKS
from .utils import py_from_ppy_filename

preprocessed_files = {}


def preprocess(
    src: Union[str, TextIO], filename: str, data: dict
) -> tuple[str, dict]:
    if not isinstance(src, str):
        src = src.read()

    # indicate that we started preprocessing
    preprocessed_files[filename] = None

    result_data = {}
    for hook in HOOKS:
        if hook.name not in data:
            data[hook.name] = hook.create_state()
        src, hook_data = hook.process(src, filename, data[hook.name])
        result_data[hook.name] = hook_data

    # save preprocessed file to display actual SyntaxError
    preprocessed_files[filename] = src

    return src, result_data


def preprocess_file(
    filename: str, save_files: bool = False
) -> Tuple[str, dict]:
    with open(filename) as f:
        res, pyc_data = preprocess(f, filename, {})
    if save_files:
        with open(py_from_ppy_filename(filename), "w") as f:
            f.write(res)
    return res, pyc_data


def maybe_preprocess(src: Any, filename: str, data: dict) -> str:
    if isinstance(src, bytes):
        src = src.decode()
    if isinstance(src, str):
        # this is essential for interactive mode
        has_newline = src.endswith("\n")
        src, _ = preprocess(src, filename, data)
        if not has_newline:
            src = src.rstrip("\n")
    return src
