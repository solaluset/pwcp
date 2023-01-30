import os

from setuptools import setup

os.environ["PWCP_IS_INSTALLING"] = "1"
from pwcp import __version__


setup(
    name="pwcp",
    version=__version__,
    packages=["pwcp"],
    install_requires=["pypp@git+https://github.com/Krutyi-4el/pypp.git"],
    entry_points={
        "console_scripts": ["pwcp=pwcp:main"],
    },
)
