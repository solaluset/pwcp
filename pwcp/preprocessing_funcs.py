from typing import Any, TextIO, Union

from .config import HOOKS

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
        src, hook_data = hook.process_source(src, filename, data[hook.name])
        result_data[hook.name] = hook_data

    # save preprocessed file to display actual SyntaxError
    preprocessed_files[filename] = src

    return src, result_data


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
