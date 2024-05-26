import os
import sys
from io import StringIO
from unittest.mock import patch
from subprocess import STDOUT, CalledProcessError, check_output

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pwcp import main
from pwcp.hooks import is_package


def test_regular_file():
    with patch("sys.stdout", new=StringIO()):
        main(["tests/hello.py"])
        assert sys.stdout.getvalue() == "Hello world! (python)\n"


def test_ppy_file():
    with patch("sys.stdout", new=StringIO()):
        main(["tests/hello.ppy"])
        assert sys.stdout.getvalue() == "Hello world!\nNone world!\n"


def test_run_module():
    with patch("sys.stdout", new=StringIO()):
        main(["-m", "tests.a_module", "1", "2", "3"])
        assert sys.stdout.getvalue() == "tests.a_module.b = 6\n"


def test_comments():
    main(["tests/comments.ppy"])


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


def test_error_directive():
    with pytest.raises(CalledProcessError) as ctx:
        check_output(
            [sys.executable, "-m", "pwcp", "tests/error_directive.ppy"],
            stderr=STDOUT,
        )
    assert ctx.value.output.splitlines()[1].strip() == b"pwcp.preprocessor.PreprocessorError: preprocessor exit code is not zero"


def test_interactive():
    s = "\nand this is a triple-quoted string\n"
    code = f"""
#define x 1
/* this
is
a comment */
'''{s}'''
def f():
    '''check whether we can declare
    a function with several lines'''
#if x
    print(x)
#endif

f()
    """.strip()
    with patch("sys.stdin", new=StringIO(code)), patch("sys.stdout", new=StringIO()):
        main(["-m", "code"])
        assert (
            sys.stdout.getvalue()
            == sys.ps1 * 2
            + sys.ps2 * 2
            + sys.ps1
            + sys.ps2 * 2
            + repr(s)
            + "\n"
            + sys.ps1
            + sys.ps2 * 6
            + sys.ps1
            + "1\n"
            + sys.ps1
        )

    code = """
#ifndef X
#define X
print(1)
#endif
    """.strip()
    with patch("sys.stdin", new=StringIO(code)), patch("sys.stdout", new=StringIO()):
        main(["-m", "code"])
        assert sys.stdout.getvalue() == sys.ps1 + sys.ps2 * 3 + "1\n" + sys.ps1


def test_overriden_compile():
    main(["tests/compile.py"])


def test_is_package():
    assert is_package("tests") is True
    assert is_package("tests.test_modules") is False
    with pytest.warns(match="Module file or directory not found"):
        assert is_package("inexistent") is False
