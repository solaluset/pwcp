import ast
from codeop import Compile


code = """
/* force preprocessing */
#pragma pypp on

#define x 1

def f():
#if !x
    return None
#else
    return x
#endif
"""

for func in (str.strip, str.encode, ast.parse):
    code_obj = compile(func(code), __file__, "exec")
    namespace = {}
    exec(code_obj, namespace)
    assert namespace["f"]() == 1

code2 = """
#pragma pypp on
#define a 1
a
"""

for func in (eval, exec):
    func(code2)

compiler = Compile()
for line in code2.splitlines():
    # should retain state between calls
    exec(compiler(line, __file__, "exec"))
