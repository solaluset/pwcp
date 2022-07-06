import argparse
import os
import sys
from importlib import util
from importlib.machinery import SourceFileLoader
from traceback import print_exception

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
    sys.path.append(os.getcwd())
    args = parser.parse_args(args)
    hooks.install(vars(args))
    if args.file.name.endswith(FILE_EXTENSION):
        loader = hooks.PPyLoader
    else:
        loader = SourceFileLoader
    spec = util.spec_from_loader(
        '__main__',
        loader('__main__', args.file.name)
    )
    module = util.module_from_spec(spec)
    sys.modules['__main__'] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        if isinstance(e, SyntaxError) and hooks.preprocessed_files.get(e.filename):
            # replace raw text from file with actual code
            data = hooks.preprocessed_files[e.filename]
            e.text = data.splitlines()[e.lineno - 1]
        tb = e.__traceback__
        # remove outer frames from traceback
        while tb and tb.tb_frame.f_code.co_filename != module.__file__:
            tb = tb.tb_next
        print_exception(type(e), e, tb)


if __name__ == '__main__':
    main()
