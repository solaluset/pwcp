from io import BytesIO
from tokenize import detect_encoding
from typing import Any

from .config import HOOKS

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
