from dynamic_default_args import *


@dynamic_default_args()
def foo(a0=named_default(a0=5),
        a1=3,
        /,
        a2=named_default(a2=slice(0, 3)),
        a3=-1,
        *a4,
        a5=None,
        a6=named_default(a6='python'),
        **a7):
    """
    A Foo function that has dynamic default arguments.

    Args:
        a0: Positional-only argument a0. Dynamically defaults to a0={a0}.
        a1: Positional-only argument a1. Defaults to {a1}.
        a2: Positional-or-keyword argument a2. Dynamically defaults to a2={a2}.
        a3: Positional-or-keyword argument a3. Defaults to {a3}
        *a4: Varargs a4.
        a5: Keyword-only argument a5. Defaults to {a5}.
        a6: Keyword-only argument a6. Dynamically defaults to {a6}.
        a7: Varkeywords a7.
    """
    print('Called with:', a0, a1, a2, a3, a4, a5, a6, a7)


def main():
    # help(foo)
    foo()
    print()

    named_default('a2').value = range(10)
    named_default('a6').value = 'rust'
    help(foo)
    foo()


if __name__ == '__main__':
    main()
