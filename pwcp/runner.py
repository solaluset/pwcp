import argparse
import os
import sys
from importlib import util
from . import hooks


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
    spec = util.spec_from_loader(
        '__main__',
        hooks.PPyLoader('__main__', args.file.name)
    )
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)


if __name__ == '__main__':
    main()
