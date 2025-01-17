"""Unittests for callsite."""

import ast
import inspect
import sys

import astor
from hamcrest import assert_that, equal_to

from . import callsite
from .basis import ID


def assert_ast(ast_node, code_str):
    assert_that(astor.to_source(ast_node).strip(), equal_to(code_str))


def test_get_callsite_ast():
    x = 1

    def f(*args, **kwargs):
        callsite_frame = sys._getframe(1)
        return callsite.get_callsite_ast(callsite_frame.f_code, callsite_frame.f_lasti)

    def g(*args, **kwargs):
        callsite_frame = sys._getframe(1)
        callsite_ast, outer_callsite_ast = callsite.get_callsite_ast(
            callsite_frame.f_code, callsite_frame.f_lasti
        )
        assert_ast(callsite_ast, "g(1, 1)")
        assert_ast(outer_callsite_ast, "f(x, g(1, 1), True if x else False)")

    callsite_ast, outer_callsite_ast = f(1)
    # We can't use assert here cause pytest will modify source and mess up things.
    assert_ast(callsite_ast, "f(1)")
    assert_that(outer_callsite_ast, equal_to(None))

    callsite_ast, outer_callsite_ast = f(1, x=2)
    # We can't use assert here cause pytest will modify source and mess up things.
    assert_ast(callsite_ast, "f(1, x=2)")
    assert_that(outer_callsite_ast, equal_to(None))

    callsite_ast, outer_callsite_ast = f(x, g(1, 1), True if x else False)
    assert_ast(callsite_ast, "f(x, g(1, 1), True if x else False)")
    assert_that(outer_callsite_ast, equal_to(None))

    # Tests multiline won't affect processing ast.
    # fmt: off
    callsite_ast, outer_callsite_ast = f(x,
                                         g(1, 1),
                                         True if x else False)
    assert_ast(callsite_ast, "f(x, g(1, 1), True if x else False)")
    assert_that(outer_callsite_ast, equal_to(None))
    # fmt: on

    def h(x):
        return x

    callsite_ast, outer_callsite_ast = h(h(h(f(1))))
    assert_ast(callsite_ast, "f(1)")
    assert_ast(outer_callsite_ast, "h(f(1))")


def _get_call(module_ast: ast.Module) -> ast.Call:
    assert isinstance(
        module_ast.body[0], ast.Expr
    ), "Passed in code is not a call expression."

    return module_ast.body[0].value


def test_get_param_to_arg():
    def f(foo, bar, baz=1, *args, **kwargs):
        return inspect.getargvalues(inspect.currentframe())

    # Tests passing values directly.
    assert callsite.get_param_to_arg(_get_call(ast.parse("f(1,2)")), f(1, 2)) == {
        ID("foo"): set(),
        ID("bar"): set(),
    }

    # Tests passing variables.
    a, b, c = 1, 2, 3
    assert callsite.get_param_to_arg(
        _get_call(ast.parse("f(a,b,c)")), f(a, b, z=c)
    ) == {ID("foo"): {ID("a")}, ID("bar"): {ID("b")}, ID("baz"): {ID("c")}}

    # Tests catching extra args.
    d, e = 4, 5
    assert callsite.get_param_to_arg(
        _get_call(ast.parse("f(a,b,c,d,qux=e)")), f(a, b, c, d, qux=e)
    ) == {
        ID("foo"): {ID("a")},
        ID("bar"): {ID("b")},
        ID("baz"): {ID("c")},
        ID("args"): {ID("d")},
        ID("kwargs"): {ID("e")},
    }

    # Tests binding multiple params to one argument.
    assert callsite.get_param_to_arg(
        _get_call(ast.parse("f(a,(b,c),c,qux=(d, e))")), f(a, (b, c), c, qux=(d, e))
    ) == {
        ID("foo"): {ID("a")},
        ID("bar"): {ID("b"), ID("c")},
        ID("baz"): {ID("c")},
        ID("kwargs"): {ID("d"), ID("e")},
    }

    # Tests using custom names for args and kwargs.
    def g(*foo, **bar):
        return inspect.getargvalues(inspect.currentframe())

    assert callsite.get_param_to_arg(
        _get_call(ast.parse("g(d,qux=e)")), g(d, qux=e)
    ) == {ID("foo"): {ID("d")}, ID("bar"): {ID("e")}}

    # Tests signature without args or kwargs.
    def h(x):
        return inspect.getargvalues(inspect.currentframe())

    assert callsite.get_param_to_arg(_get_call(ast.parse("h(a)")), h(a)) == {
        ID("x"): {ID("a")}
    }

    # TODO: tests nested call.
