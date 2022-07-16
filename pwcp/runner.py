import argparse
import os
import sys
from importlib import util
from importlib.machinery import SourceFileLoader

from . import hooks
from .config import FILE_EXTENSION


parser = argparse.ArgumentParser(description="Python with C preprocessor")
parser.add_argument(
    '--prefer-py',
    dest='prefer_python',
    action='store_true',
    help='Prefer .py files over .ppy when importing.'
)
parser.add_argument(
    '--save-files',
    dest='save_files',
    action='store_true',
    help='Save .ppy files to .py after preprocessing.'
)
parser.add_argument('file', type=argparse.FileType('r'))


def main(args=sys.argv[1:]):
    args = parser.parse_args(args)
    hooks.install(vars(args))
    filename: str = args.file.name
    sys.path.insert(0, os.path.dirname(os.path.abspath(filename)))
    if filename.endswith(FILE_EXTENSION):
        loader = hooks.PPyLoader
    else:
        loader = SourceFileLoader
    spec = util.spec_from_loader(
        '__main__',
        loader('__main__', filename)
    )
    module = util.module_from_spec(spec)
    sys.modules['__main__'] = module
    sys.excepthook = hooks.create_exception_handler(module)
    spec.loader.exec_module(module)


if __name__ == '__main__':
    main()
