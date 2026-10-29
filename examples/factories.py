"""Run with: python examples/factories.py (after installing the package)."""
from dynamic_default_args import default_factory, dynamic_default_args


@dynamic_default_args
def take(items, limit=default_factory(len, depends_on=("items",)), *,
         output=default_factory(list)):
    output.extend(items[:limit])
    return output


class Client:
    def __init__(self, timeout):
        self.timeout = timeout

    @dynamic_default_args
    def request(self, timeout=default_factory(lambda self: self.timeout,
                                              depends_on=("self",))):
        return timeout


if __name__ == "__main__":
    print(take([1, 2, 3]))
    print(take([1, 2, 3], 1))
    print(Client(10).request())
