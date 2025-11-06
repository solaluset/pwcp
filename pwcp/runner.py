import os
import sys
import argparse
from typing import Iterable
from functools import partial
from importlib import util
from importlib.machinery import SourceFileLoader

from . import hooks
from .config import FILE_EXTENSIONS
from .version import __version__
from .utils import create_exception_handler, is_package


parser = argparse.ArgumentParser(
    (
        "python -m " + __package__
        if sys.argv[0] == "-m"
        else os.path.basename(sys.argv[0])
    ),
    description="Python with C preprocessor",
)
parser.add_argument(
    "--version", action="version", version="pwcp " + __version__
)
parser.add_argument("-m", action="store_true", help="run target as module")
parser.add_argument(
    "-c", action="store_true", help="run target as command line"
)
parser.add_argument(
    "--PP",
    "--prefer-py",
    dest="prefer_python",
    action="store_true",
    help="prefer .py files over .ppy when importing",
)
parser.add_argument(
    "--SF",
    "--save-files",
    dest="save_files",
    action="store_true",
    help="save .ppy files to .py after preprocessing",
)
parser.add_argument(
    "--PUS",
    "--preprocess-unknown-sources",
    dest="preprocess_unknown_sources",
    action="store_true",
    help="preprocess code even if filename is unknown"
    " (for example, in exec call)",
)
parser.add_argument("target")
parser.add_argument("args", nargs=argparse.REMAINDER)


def main_with_params(
    *,
    target: str,
    args: Iterable[str],
    m: bool,
    c: bool,
    prefer_python: bool,
    save_files: bool,
    preprocess_unknown_sources: bool,
):
    hooks.install(
        prefer_python=prefer_python,
        save_files=save_files,
        preprocess_unknown_sources=preprocess_unknown_sources,
    )
    if not m:
        filename: str
        if not c:
            filename = os.path.abspath(target)
            sys.path.insert(0, os.path.dirname(filename))
            if filename.endswith(tuple(FILE_EXTENSIONS)):
                loader = hooks.PPyLoader
            else:
                loader = SourceFileLoader
        else:
            sys.path.insert(0, os.getcwd())
            filename = "-c"
            loader = partial(hooks.PPyLoader, command_line=target)
        spec = util.spec_from_loader(
            "__main__",
            loader("__main__", filename),
        )
        vars_override = {"__package__": None}
    else:
        sys.path.insert(0, os.getcwd())
        if is_package(target):
            target += ".__main__"
        spec = util.find_spec(target)
        if spec is None:
            print("No module named " + target)
            return
        spec.loader.name = "__main__"
        vars_override = {"__name__": "__main__"}
    module = util.module_from_spec(spec)
    vars(module).update(vars_override)
    sys.modules["__main__"] = module
    sys.excepthook = create_exception_handler(module)
    orig_argv = sys.argv.copy()
    sys.argv.clear()
    sys.argv.append(module.__file__)
    sys.argv.extend(args)

    spec.loader.exec_module(module)

    sys.argv.clear()
    sys.argv.extend(orig_argv)
    del sys.path[0]


def main(args=sys.argv[1:]):
    args = parser.parse_args(args)
    main_with_params(**vars(args))


if __name__ == "__main__":
    main()
