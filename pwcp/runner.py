import argparse
import os
import sys
from collections.abc import Iterable
from functools import partial
from importlib import util

from . import importers
from .utils import create_exception_handler, is_package
from .version import __version__

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
    "--prefer-python",
    dest="prefer_python",
    action="store_true",
    help="prefer .py files over .ppy when importing",
)
parser.add_argument(
    "--save-files",
    dest="save_files",
    action="store_true",
    help="save .ppy files to .py after preprocessing;"
    " only useful for debugging because caching is done in `.pyc`s",
)
parser.add_argument(
    "--skip-unknown-sources",
    dest="skip_unknown_sources",
    action="store_true",
    help="do not preprocess code if filename is not recognized"
    " (for example, in exec call)",
)
parser.add_argument(
    "--no-exception-trimming",
    dest="no_exception_trimming",
    action="store_true",
    help="do not remove outer (PWCP code's) exception frames",
)
parser.add_argument("target")
parser.add_argument("args", nargs=argparse.REMAINDER)


def main_with_params(
    *,
    target: str,
    args: Iterable[str] = (),
    m: bool = False,
    c: bool = False,
    prefer_python: bool = False,
    save_files: bool = False,
    skip_unknown_sources: bool = False,
    no_exception_trimming: bool = False,
):
    importers.install(
        prefer_python=prefer_python,
        save_files=save_files,
        skip_unknown_sources=skip_unknown_sources,
    )
    if not m:
        filename: str
        if not c:
            filename = os.path.abspath(target)
            sys.path.insert(0, os.path.dirname(filename))
            loader = importers.PPyLoader
        else:
            filename = "-c"
            sys.path.insert(0, "")
            loader = partial(importers.PPyLoader, command_line=target)
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
    sys.excepthook = create_exception_handler(
        None if no_exception_trimming else module
    )
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
