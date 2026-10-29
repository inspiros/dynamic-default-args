"""Generate wrappers with native Python argument binding."""
from functools import partial, update_wrapper
import inspect
import re
import sys
from types import FunctionType
from typing import Callable, Mapping, Optional, ParamSpec, TypeVar, overload

from .defaults import default, default_factory, named_default

__all__ = ["default", "named_default", "default_factory", "dynamic_default_args"]
_P = ParamSpec("_P")
_R = TypeVar("_R")
_MARKERS = (default, default_factory)
_EMPTY = inspect.Parameter.empty


class _Source:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def _binding_signature(target):
    if sys.version_info >= (3, 14) and inspect.isfunction(target):
        target = inspect.unwrap(target, stop=lambda f: getattr(f, "__signature__", None) is not None)
        if inspect.isfunction(target) and getattr(target, "__signature__", None) is None:
            # Even annotationlib's STRING format may execute annotation code.
            # A temporary function view gives inspect only binding metadata.
            view = FunctionType(target.__code__, target.__globals__, target.__name__,
                                target.__defaults__, target.__closure__)
            view.__kwdefaults__ = target.__kwdefaults__
            return inspect.signature(view)
    return inspect.signature(target)


def _format_doc(wrapper, signature):
    template = wrapper.__doc__
    if not template:
        return
    values = {p.name: p.default for p in signature.parameters.values()
              if p.default is not _EMPTY and not isinstance(p.default, default_factory)}
    if not values:
        return
    # Substitute only known simple fields; preserve JSON and escaped braces.
    fields = "|".join(re.escape(name) for name in values)
    pattern = re.compile(r"(?<!\{)\{(" + fields + r")(![rsa])?(:[^{}]*)?\}(?!\})")
    used = {match.group(1) for match in pattern.finditer(template)}
    if not used:
        return

    def update(*_args, **_kwargs):
        current = {name: values[name].value if isinstance(values[name], default)
                   else values[name] for name in used}
        wrapper.__doc__ = pattern.sub(
            lambda match: match.group(0).format_map(current), template)

    wrapper.__default_doc__ = template
    wrapper.__dynamic_doc_updater__ = update
    update()
    for name in used:
        if isinstance(values[name], default):
            values[name].connect(update, weak=True)


def _has_doc_fields(target, signature):
    template = getattr(target, "__doc__", None)
    if not template:
        return False
    return any(re.search(r"(?<!\{)\{" + re.escape(p.name) + r"(?:![rsa])?(?::[^{}]*)?\}(?!\})", template)
               for p in signature.parameters.values() if p.default is not _EMPTY)


@overload
def dynamic_default_args(func: Callable[_P, _R], *, format_doc: bool = True,
                         force_wrap: bool = False, defaults: Optional[Mapping] = None,
                         signature: Optional[inspect.Signature] = None) -> Callable[_P, _R]: ...


@overload
def dynamic_default_args(func: None = None, *, format_doc: bool = True,
                         force_wrap: bool = False, defaults: Optional[Mapping] = None,
                         signature: Optional[inspect.Signature] = None
                         ) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]: ...


def dynamic_default_args(func=None, *, format_doc=True, force_wrap=False,
                         defaults=None, signature=None):
    """Resolve shared values and factories only for omitted arguments.

    ``defaults={name: marker}`` supplies defaults outside a function definition,
    including for Cython functions with C-typed parameters. An explicit
    ``inspect.Signature`` can adapt callables without signature metadata.
    """
    if isinstance(func, bool):  # Legacy positional format_doc option.
        format_doc, func = func, None

    def decorate(target):
        if isinstance(target, (classmethod, staticmethod)):
            return type(target)(decorate(target.__func__))
        if inspect.ismethod(target) and signature is None:
            return decorate(target.__func__).__get__(target.__self__, type(target.__self__))
        if not callable(target):
            raise TypeError("dynamic_default_args requires a callable")
        if signature is not None and not isinstance(signature, inspect.Signature):
            raise TypeError("signature must be an inspect.Signature")
        try:
            if signature is not None:
                original = signature
            else:
                original = _binding_signature(target)
        except (TypeError, ValueError) as exc:
            raise TypeError("Cannot inspect callable; supply signature=inspect.Signature(...)") from exc
        parameters = dict(original.parameters)
        overrides = {} if defaults is None else dict(defaults)
        for name, marker in overrides.items():
            if name not in parameters:
                raise ValueError(f"Unknown parameter: {name}")
            if not isinstance(marker, _MARKERS):
                raise TypeError(f"Default for {name} must be default or default_factory")
            if parameters[name].kind in (inspect.Parameter.VAR_POSITIONAL,
                                          inspect.Parameter.VAR_KEYWORD):
                raise ValueError("Variadic parameters cannot have dynamic defaults")
            parameters[name] = parameters[name].replace(default=marker)
        try:
            public_signature = original.replace(parameters=parameters.values())
        except ValueError as exc:
            raise ValueError(f"Dynamic defaults produce an invalid signature: {exc}") from exc
        dynamic = []
        earlier = set()
        for parameter in parameters.values():
            marker = parameter.default
            if isinstance(marker, _MARKERS):
                dependencies = marker.depends_on if isinstance(marker, default_factory) else ()
                if any(name not in earlier for name in dependencies):
                    raise ValueError(f"Factory for {parameter.name} must depend on earlier parameters")
                dynamic.append((parameter.name, marker, dependencies))
            earlier.add(parameter.name)
        if not dynamic and not force_wrap and signature is None:
            if not format_doc or not _has_doc_fields(target, public_signature):
                return target
        expose_signature = bool(overrides) or signature is not None
        if expose_signature and signature is None and sys.version_info >= (3, 14):
            # An override needs an explicit public signature. Prefer evaluated
            # annotations when available, and keep strings for forward references.
            try:
                evaluated = inspect.signature(target)
            except NameError:
                from annotationlib import Format
                evaluated = inspect.signature(target, annotation_format=Format.STRING)
            public_signature = evaluated.replace(parameters=[
                p.replace(default=parameters[p.name].default)
                for p in evaluated.parameters.values()])
        wrapper = _make_wrapper(target, public_signature, dynamic, expose_signature)
        if format_doc:
            _format_doc(wrapper, public_signature)
        return wrapper

    return decorate if func is None else decorate(func)


def _make_wrapper(target, signature, dynamic, expose_signature):
    parameters = list(signature.parameters.values())
    prefix = "_dda_"
    while any(p.name.startswith(prefix) for p in parameters):
        prefix = "_" + prefix
    alias = lambda name: prefix + name
    missing = object()
    dynamic_names = {name for name, _, _ in dynamic}
    context = {alias("target"): target, alias("missing"): missing,
               alias("defaults"): tuple(p.default for p in parameters),
               alias("resolvers"): tuple(marker._resolve for _, marker, _ in dynamic),
               alias("StopAsyncIteration"): StopAsyncIteration,
               alias("GeneratorExit"): GeneratorExit, alias("BaseException"): BaseException}
    rendered = []
    forwarded = []
    for index, parameter in enumerate(parameters):
        value = parameter.default
        if value is not _EMPTY:
            value = _Source(alias("missing") if parameter.name in dynamic_names
                            else f"{alias('defaults')}[{index}]")
        rendered.append(parameter.replace(default=value, annotation=_EMPTY))
        if parameter.kind is parameter.VAR_POSITIONAL:
            forwarded.append("*" + parameter.name)
        elif parameter.kind is parameter.VAR_KEYWORD:
            forwarded.append("**" + parameter.name)
        elif parameter.kind is parameter.KEYWORD_ONLY:
            forwarded.append(f"{parameter.name}={parameter.name}")
        else:
            forwarded.append(parameter.name)
    definition_signature = inspect.Signature(rendered)
    kind_target = (target if inspect.isroutine(target) or isinstance(target, partial)
                   else target.__call__)
    is_asyncgen = inspect.isasyncgenfunction(kind_target)
    is_coroutine = inspect.iscoroutinefunction(kind_target)
    is_generator = inspect.isgeneratorfunction(kind_target)
    keyword = "async def" if is_coroutine or is_asyncgen else "def"
    lines = [f"{keyword} {alias('wrapper')}{definition_signature}:"]
    for index, (name, marker, dependencies) in enumerate(dynamic):
        lines += [f"    if {name} is {alias('missing')}:",
                  f"        {name} = {alias('resolvers')}[{index}]({', '.join(dependencies)})"]
    call = f"{alias('target')}({', '.join(forwarded)})"
    if is_asyncgen:
        gen, item, sent, error = map(alias, ("gen", "item", "sent", "error"))
        lines += [f"    {gen} = {call}", "    try:",
                  f"        {item} = await {gen}.__anext__()", "        while True:",
                  "            try:", f"                {sent} = yield {item}",
                  f"            except {alias('GeneratorExit')}:",
                  f"                await {gen}.aclose()", "                raise",
                  f"            except {alias('BaseException')} as {error}:",
                  f"                {item} = await {gen}.athrow({error})",
                  "            else:", f"                {item} = await {gen}.asend({sent})",
                  f"    except {alias('StopAsyncIteration')}:", "        return",
                  "    finally:", f"        await {gen}.aclose()"]
    elif is_coroutine:
        lines.append(f"    return await {call}")
    elif is_generator:
        lines.append(f"    return (yield from {call})")
    else:
        lines.append(f"    return {call}")
    exec(compile("\n".join(lines), "<dynamic-default-args wrapper>", "exec"), context)
    wrapper = update_wrapper(context[alias("wrapper")], target)
    if expose_signature:
        wrapper.__signature__ = signature
    return wrapper
