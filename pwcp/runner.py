import argparse
import os
import sys
from importlib import util
from importlib.machinery import SourceFileLoader

try:
    from . import hooks
except ImportError:
    # ignore error when we only need version
    if not os.getenv("PWCP_IS_INSTALLING"):
        raise
from .config import FILE_EXTENSION


__version__ = "0.5b0"

parser = argparse.ArgumentParser(
    "python -m " + __package__
    if sys.argv[0] == "-m"
    else os.path.basename(sys.argv[0]),
    description="Python with C preprocessor",
)
parser.add_argument("--version", action="version", version="pwcp " + __version__)
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
        if filename.endswith(FILE_EXTENSION):
            loader = hooks.PPyLoader
        else:
            loader = SourceFileLoader
        spec = util.spec_from_loader(
            "__main__",
            loader("__main__", filename),
        )
    else:
        sys.path.insert(0, os.getcwd())
        if hooks.is_package(args.target):
            args.target += ".__main__"
        spec = util.find_spec(args.target)
        if spec is None:
            print("No module named " + args.target)
            return
        spec.loader.name = "__main__"
    module = util.module_from_spec(spec)
    module.__name__ = "__main__"
    sys.modules["__main__"] = module
    sys.excepthook = hooks.create_exception_handler(module)
    orig_argv = sys.argv.copy()
    sys.argv.clear()
    sys.argv.append(module.__file__)
    sys.argv.extend(args.args)

    spec.loader.exec_module(module)

    sys.argv.clear()
    sys.argv.extend(orig_argv)


if __name__ == "__main__":
    main()
