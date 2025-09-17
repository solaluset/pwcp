import ast


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

for func in (eval, exec):
    func(
        """
#pragma pypp on
#define a 1
a
    """
    )
