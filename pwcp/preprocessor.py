from pcpp import Preprocessor
from io import StringIO
from os import path
from .config import FILE_EXTENSION


def preprocess(filename, config={}):
    p = Preprocessor(fix_indentation=True)
    with open(filename) as f:
        p.parse(f)
    out = StringIO()
    p.write(out)
    out.seek(0)
    res = out.read()
    if config.get("save_files"):
        dir, file = path.split(filename)
        if file.endswith(FILE_EXTENSION):
            file = file.rpartition(".")[0] + ".py"
        else:
            file += ".py"
        with open(path.join(dir, file), "w") as f:
            f.write(res)
    return res
