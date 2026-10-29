"""Compile with Cython 3 using binding=True (the default)."""
from dynamic_default_args import default, dynamic_default_args

scale = default(2.0)

@dynamic_default_args(defaults={"x": scale})
def compute(double x=0.0):
    return x * 2

cpdef double native_compute(double x=0.0):
    return x * 2

# Python callers use this name; compiled calls to native_compute bypass it.
compute_dual = dynamic_default_args(defaults={"x": scale})(native_compute)
