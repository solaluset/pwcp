import os
import sys
import time
import _imp
import py_compile
from io import StringIO
from unittest.mock import patch
from subprocess import STDOUT, CalledProcessError, check_output

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from pwcp import main  # noqa: E402
from pwcp.utils import is_package  # noqa: E402


sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


def test_regular_file():
    with patch("sys.stdout", new=StringIO()):
        # -h should be treated as argument to file, not PWCP
        # and therefore ignored
        main(["tests/hello.py", "-h"])
        assert sys.stdout.getvalue() == "Hello world! (python)\n"


def test_ppy_file():
    with patch("sys.stdout", new=StringIO()):
        main(["tests/hello.ppy"])
        assert sys.stdout.getvalue() == "Hello world!\nNone world!\n"


def test_run_module():
    with patch("sys.stdout", new=StringIO()):
        main(["-m", "tests.a_module", "1", "2", "3"])
        assert sys.stdout.getvalue() == "tests.a_module.b = 6\n"


def test_run_command():
    with patch("sys.stdout", new=StringIO()):
        main(["--preprocess-unknown-sources", "-c", "print(__LINE__)"])
        assert sys.stdout.getvalue() == "1\n"


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
    assert ctx.value.output.splitlines()[-3].strip() == b'print("hello")!'


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
    assert (
        ctx.value.output.splitlines()[-1].strip()
        == b"pwcp.errors.PreprocessorError:"
        b" preprocessor exit code is not zero: 1"
    )


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
    with patch("sys.stdin", new=StringIO(code)), patch(
        "sys.stdout", new=StringIO()
    ):
        ps1 = getattr(sys, "ps1", ">>> ")
        ps2 = getattr(sys, "ps2", "... ")
        main(["--preprocess-unknown-sources", "-m", "code"])
        assert (
            sys.stdout.getvalue()
            == ps1 * 2
            + ps2 * 2
            + ps1
            + ps2 * 2
            + repr(s)
            + "\n"
            + ps1
            + ps2 * 6
            + ps1
            + "1\n"
            + ps1
        )

    code = """
#ifndef X
#define X
print(1)
#endif
    """.strip()
    with patch("sys.stdin", new=StringIO(code)), patch(
        "sys.stdout", new=StringIO()
    ):
        main(["--preprocess-unknown-sources", "-m", "code"])
        assert sys.stdout.getvalue() == ps1 + ps2 * 3 + "1\n" + ps1


def test_overriden_compile():
    main(["tests/compile.py"])


@patch("time.strftime")
def _test_bytecode_caching(output_override, patched_strftime):
    sys.dont_write_bytecode = False
    try:
        hello1 = "Hello, this file was cached at "
        hello2 = "Just hello."

        with open("tests/bytecode_test.pyh", "w") as f:
            f.write(f"#define HELLO {hello1!r} __TIME__")

        patched_strftime.return_value = "10:10:10"

        if output_override is None:
            time_str = time.strftime("%H:%M:%S")
            hello1_full = hello1 + time_str + "\n"
            hello2_full = hello2 + "\n"
        else:
            hello1_full = hello2_full = output_override

        with patch("sys.stdout", new=StringIO()):
            main(["tests/bytecode_test.ppy"])
            assert sys.stdout.getvalue() == hello1_full

        patched_strftime.return_value = "20:20:20"

        with patch("sys.stdout", new=StringIO()):
            main(["tests/bytecode_test.ppy"])
            assert sys.stdout.getvalue() == hello1_full

        time.sleep(0.01)

        with open("tests/bytecode_test.pyh", "w") as f:
            f.write(f"#define HELLO {hello2!r}")

        with patch("sys.stdout", new=StringIO()):
            main(["tests/bytecode_test.ppy"])
            assert sys.stdout.getvalue() == hello2_full
    finally:
        sys.dont_write_bytecode = True


@pytest.mark.parametrize("mode", py_compile.PycInvalidationMode)
def test_bytecode_caching(mode):
    assert _imp.check_hash_based_pycs == "default"

    pyc1 = py_compile.compile(
        "tests/hello.py", invalidation_mode=mode, doraise=True
    )
    pyc2 = pyc1.replace("hello", "bytecode_test")
    os.rename(pyc1, pyc2)
    del pyc1

    try:
        _test_bytecode_caching(
            "Hello world! (python)\n"
            if mode == py_compile.PycInvalidationMode.UNCHECKED_HASH
            else None
        )
    finally:
        os.remove(pyc2)


def test_is_package():
    assert is_package("tests") is True
    assert is_package("tests.test_modules") is False
    with pytest.warns(match="Module file or directory not found"):
        assert is_package("inexistent") is False
