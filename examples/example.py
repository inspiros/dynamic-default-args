from dynamic_default_args import *


@dynamic_default_args()
def foo(a0,
        a1=named_default(a1=5),
        a2=3,
        /,
        a3=named_default(a3=slice(0, 3)),
        a4=-1,
        *a5,
        a6=None,
        a7=named_default(a7='python'),
        **a8):
    """
    A Foo function that has dynamic default arguments.

    Args:
        a0: Required Positional-only argument a0.
        a1: Positional-only argument a1. Dynamically defaults to a0={a1}.
        a2: Positional-only argument a1. Defaults to {a2}.
        a3: Positional-or-keyword argument a2. Dynamically defaults to a3={a3}.
        a4: Positional-or-keyword argument a4. Defaults to {a4}
        *a5: Varargs a5.
        a6: Keyword-only argument a5. Defaults to {a6}.
        a7: Keyword-only argument a6. Dynamically defaults to {a7}.
        **a8: Varkeywords a8.
    """
    print(f'Called with: a0={a0}, a1={a1}, a2={a2}, a3={a3}, '
          f'a4={a4}, a5={a5}, a6={a6}, a7={a7}, a8={a8}')


def main():
    help(foo)
    foo(0)
    print()

    # modify defaults' values
    named_default('a1').value *= 2
    named_default('a3').value = range(10)
    named_default('a7').value = 'rust'

    help(foo)
    foo(foo, a6=..., a9=1.5)


if __name__ == '__main__':
    main()
