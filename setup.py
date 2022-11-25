import os

from setuptools import setup

os.environ["PWCP_IS_INSTALLING"] = "1"
from pwcp import __version__


setup(
    name="pwcp",
    version=__version__,
    packages=["pwcp"],
    install_requires=["pcpp@git+https://github.com/Krutyi-4el/pcpp.git"],
    entry_points={
        "console_scripts": ["pwcp=pwcp:main"],
    },
)
