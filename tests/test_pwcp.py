import os
import sys
from io import StringIO
from unittest.mock import patch
from subprocess import STDOUT, CalledProcessError, check_output

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pwcp import main


def test_regular_file():
    with patch("sys.stdout", new=StringIO()):
        main(["tests/hello.py"])
        assert sys.stdout.getvalue() == "Hello world! (python)\n"


def test_ppy_file():
    with patch("sys.stdout", new=StringIO()):
        main(["tests/hello.ppy"])
        assert sys.stdout.getvalue() == "Hello world!\n"


def test_comment_preservation():
    main(["tests/not_a_comment.ppy"])


def test_imports():
    main(["tests/test_modules.ppy"])
    assert sys.modules["hello"].__file__ == os.path.join(
        os.path.abspath("tests"), "hello.ppy"
    )
    del sys.modules["hello"]


def test_py_import():
    main(["--prefer-py", "tests/test_modules.ppy"])
    assert sys.modules["hello"].__file__ == os.path.join(
        os.path.abspath("tests"), "hello.py"
    )
    del sys.modules["hello"]


def test_syntax_error():
    with pytest.raises(CalledProcessError) as ctx:
        check_output(
            [sys.executable, "-m", "pwcp", "tests/syntax_error.ppy"],
            stderr=STDOUT,
        )
    assert ctx.value.output.splitlines()[1].strip() == b'print("hello")!'


def test_type_error():
    with pytest.raises(CalledProcessError) as ctx:
        check_output(
            [sys.executable, "-m", "pwcp", "tests/type_error.ppy"],
            stderr=STDOUT,
        )
    assert ctx.value.output.splitlines()[2].strip() == b"print('1' + 1)"
