import os
import sys
import shutil

import setuptools
import ppsetuptools
from setuptools import setup

sys.path.append("pwcp")
from version import __version__  # noqa: E402

del sys.path[-1]

here = os.path.abspath(os.path.dirname(__file__))
shutil.copy2(os.path.join(here, "LICENSE.md"), os.path.join(here, "pwcp"))


def patched_setup(*args, **kwargs):
    scripts = kwargs.pop("scripts")
    kwargs["entry_points"] = {
        "console_scripts": [f"{k}={v}" for k, v in scripts.items()]
    }
    setup(*args, **{k: v for k, v in kwargs.items() if v is not None})


setuptools.setup = patched_setup
ppsetuptools.setup(
    version=__version__,
    packages=["pwcp"],
    license="MIT" if sys.version_info >= (3, 9) else None,
)
