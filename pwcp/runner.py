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


__version__ = "0.4b2"

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
parser.add_argument("file", type=argparse.FileType("r"))


def main(args=sys.argv[1:]):
    args = parser.parse_args(args)
    hooks.install(vars(args))
    filename: str = os.path.abspath(args.file.name)
    sys.path.insert(0, os.path.dirname(filename))
    if filename.endswith(FILE_EXTENSION):
        loader = hooks.PPyLoader
    else:
        loader = SourceFileLoader
    spec = util.spec_from_loader(
        "__main__",
        loader("__main__", filename),
    )
    module = util.module_from_spec(spec)
    sys.modules["__main__"] = module
    sys.excepthook = hooks.create_exception_handler(module)
    spec.loader.exec_module(module)


if __name__ == "__main__":
    main()
