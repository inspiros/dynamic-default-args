from dynamic_default_args import default, default_factory, dynamic_default_args

cell = default(1.0)

@dynamic_default_args()
def untyped(x=cell):
    return x

@dynamic_default_args(defaults={"x": cell})
def typed(double x=0.0):
    return x

def mixed(static=None, double x=0.0, *, key=None):
    return static, x, key

@dynamic_default_args(defaults={"x": default_factory(lambda: 3.5)})
def annotated(x: float = 0.0):
    return x

cpdef double dual(double x=0.0):
    return x

wrapped_dual = dynamic_default_args(defaults={"x": cell})(dual)

def native_call():
    return dual()

class PythonClass:
    @dynamic_default_args(defaults={"x": cell})
    def method(self, double x=0.0):
        return x

cdef class ExtensionClass:
    def method(self, double x=0.0):
        return x
