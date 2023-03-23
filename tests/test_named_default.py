import random

from dynamic_default_args import named_default
import unittest


def _init_with_unregistered_name():
    return named_default('x')


def _init_with_3_positional_args():
    return named_default('x', random.random(), random.random())


def _init_with_2_keyword_args():
    return named_default(x=random.random(), y=random.random())


def _init_with_name_and_1_keyword_arg():
    return named_default(name='x', z=random.random())


def _init_with_value_and_1_keyword_arg():
    return named_default(value=random.random(), x=random.random())


class NamedDefaultTest(unittest.TestCase):
    def test_init_with_2_positional_args(self):
        name, value = 'x0', random.random()
        x = named_default(name, value)
        self.assertEqual(x.value, value)

    def test_init_with_name_positional_and_value_keyword(self):
        name, value = 'x1', random.random()
        x = named_default(name, value=value)
        self.assertEqual(x.value, value)

    def test_init_with_name_and_value_keywords(self):
        name, value = 'x2', random.random()
        x = named_default(name=name, value=value)
        self.assertEqual(x.value, value)

    def test_init_with_one_keyword_arg(self):
        name, value = 'x3', random.random()
        x = named_default(**{name: value})
        self.assertEqual(x.value, value)

    def test_init_with_unregistered_name(self):
        self.assertRaises(ValueError, _init_with_unregistered_name)

    def test_init_with_3_positional_args(self):
        self.assertRaises(TypeError, _init_with_3_positional_args)

    def test_init_with_2_keyword_args(self):
        self.assertRaises(ValueError, _init_with_2_keyword_args)

    def test_init_with_name_and_1_keyword_arg(self):
        self.assertRaises(ValueError, _init_with_name_and_1_keyword_arg)

    def test_init_with_value_and_1_keyword_arg(self):
        self.assertRaises(ValueError, _init_with_value_and_1_keyword_arg)

    def test_retrieve_registered_name(self):
        name, value = 'y0', random.random()
        named_default(name, value)
        self.assertEqual(named_default(name).value, value)
        self.assertEqual(named_default(name), value)

    def test_init_with_registered_name_and_new_value(self):
        name, value = 'y1', random.random()
        named_default(name, value)
        named_default(name, value + 1)
        self.assertNotEqual(named_default(name).value, value + 1)
        self.assertEqual(named_default(name).value, value)

    def test_modify_value(self):
        name, value = 'y2', random.random()
        named_default(name, value)

        new_value = random.random()
        named_default(name).value = new_value
        self.assertEqual(named_default(name).value, new_value)

        named_default(name).value *= 2
        self.assertEqual(named_default(name).value, new_value * 2)


if __name__ == '__main__':
    unittest.main()
