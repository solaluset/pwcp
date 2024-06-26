import argparse
import os
import sys
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
parser.add_argument(
    "--prefer-py",
    dest="prefer_python",
    action="store_true",
    help="Prefer .py files over .ppy when importing.",
)
parser.add_argument(
    "--save-files",
    dest="save_files",
    action="store_true",
    help="Save .ppy files to .py after preprocessing.",
)
parser.add_argument("-m", action="store_true", help="Run target as module")
parser.add_argument("target")
parser.add_argument("args", nargs=argparse.ZERO_OR_MORE)


def main(args=sys.argv[1:]):
    args = parser.parse_args(args)
    hooks.install(vars(args))
    if not args.m:
        filename: str = os.path.abspath(args.target)
        sys.path.insert(0, os.path.dirname(filename))
        if filename.endswith(tuple(FILE_EXTENSIONS)):
            loader = hooks.PPyLoader
        else:
            loader = SourceFileLoader
        spec = util.spec_from_loader(
            "__main__",
            loader("__main__", filename),
        )
        vars_override = {"__package__": None}
    else:
        sys.path.insert(0, os.getcwd())
        if is_package(args.target):
            args.target += ".__main__"
        spec = util.find_spec(args.target)
        if spec is None:
            print("No module named " + args.target)
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
    sys.argv.extend(args.args)

    spec.loader.exec_module(module)

    sys.argv.clear()
    sys.argv.extend(orig_argv)


if __name__ == "__main__":
    main()
