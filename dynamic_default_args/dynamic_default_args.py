"""Generate wrappers with native Python argument binding."""
from functools import partial, update_wrapper
import inspect
import re
import sys
from types import FunctionType, MethodType
from typing import TYPE_CHECKING, Callable, Mapping, Optional, TypeVar, overload

from .defaults import _callable_target, default, default_factory, named_default

__all__ = ["default", "named_default", "default_factory", "dynamic_default_args"]
if TYPE_CHECKING or sys.version_info >= (3, 10):
    from typing import ParamSpec
    _P = ParamSpec("_P")
else:  # Before 3.10, the runtime hints degrade to Callable[..., _R].
    _P = ...
_R = TypeVar("_R")
_MARKERS = (default, default_factory)
_EMPTY = inspect.Parameter.empty


class _Source:
    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def _annotation_free_view(target):
    if getattr(target, "__signature__", None) is not None:
        return target
    if inspect.ismethod(target):
        return MethodType(_annotation_free_view(target.__func__), target.__self__)
    unwrapped = inspect.unwrap(target, stop=lambda f: getattr(f, "__signature__", None) is not None)
    if unwrapped is not target:
        return _annotation_free_view(unwrapped)
    if isinstance(target, partial):
        return partial(_annotation_free_view(target.func), *target.args, **target.keywords)
    if inspect.isfunction(target):
        # Even annotationlib's STRING format may execute annotation code.
        # A temporary function view gives inspect only binding metadata.
        view = FunctionType(target.__code__, target.__globals__, target.__name__,
                            target.__defaults__, target.__closure__)
        view.__kwdefaults__ = target.__kwdefaults__
        return view
    elif not inspect.isroutine(target) and not inspect.isclass(target):
        return _annotation_free_view(_callable_target(target))
    return target


def _binding_signature(target):
    view = _annotation_free_view(target) if sys.version_info >= (3, 14) else target
    return inspect.signature(view)


def _bound_arguments(target):
    """Recover dependency values hidden by method and partial binding."""
    if isinstance(target, partial):
        values = _bound_arguments(target.func)
        base_signature = _binding_signature(target.func)
        bound = base_signature.bind_partial(*target.args, **target.keywords)
        for name, value in bound.arguments.items():
            kind = base_signature.parameters[name].kind
            if kind is inspect.Parameter.VAR_POSITIONAL:
                value = values.get(name, ()) + value
            elif kind is inspect.Parameter.VAR_KEYWORD:
                value = {**values.get(name, {}), **value}
            values[name] = value
        return values
    if inspect.ismethod(target):
        parameters = iter(_binding_signature(target.__func__).parameters)
        name = next(parameters, None)
        return {name: target.__self__} if name is not None else {}
    if not inspect.isroutine(target) and not inspect.isclass(target):
        return _bound_arguments(_callable_target(target))
    return {}


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

        def render(match):
            try:
                return match.group(0).format_map(current)
            except Exception:  # Docs must never break assignment to a shared value.
                return match.group(0)

        wrapper.__doc__ = pattern.sub(render, template)

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
            wrapped = decorate(target.__func__)
            return target if wrapped is target.__func__ else type(target)(wrapped)
        if inspect.ismethod(target) and signature is None:
            wrapped = decorate(target.__func__)
            return (target if wrapped is target.__func__ else
                    wrapped.__get__(target.__self__, type(target.__self__)))
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
        bound_arguments = {} if signature is not None else _bound_arguments(target)
        bound_values = {name: value for name, value in bound_arguments.items()
                        if name not in parameters}
        prefixes = {name: value for name, value in bound_arguments.items()
                    if name in parameters
                    and parameters[name].kind is inspect.Parameter.VAR_POSITIONAL}
        earlier = set(bound_values)
        for parameter in parameters.values():
            marker = parameter.default
            explicitly_bound = parameter.name in bound_arguments and parameter.name not in overrides
            if isinstance(marker, _MARKERS) and not explicitly_bound:
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
        wrapper = _make_wrapper(target, public_signature, dynamic, expose_signature,
                                bound_values, prefixes, preserve_omissions=signature is None)
        if format_doc:
            _format_doc(wrapper, public_signature)
        return wrapper

    return decorate if func is None else decorate(func)


def _forwarding_lines(parameters, static_names, alias, indent):
    """Keep static omissions, filling only unavoidable positional-only gaps."""
    args, kwargs, positional, last = map(alias, ("args", "kwargs", "positional", "last"))
    missing = alias("missing")
    lines = [f"{args} = []", f"{kwargs} = {{}}", f"{positional} = True"]
    positional_only = [p for p in parameters if p.kind is p.POSITIONAL_ONLY]
    if any(p.name in static_names for p in positional_only):
        lines.append(f"{last} = -1")
        for index, parameter in enumerate(positional_only):
            if parameter.name not in static_names:
                lines.append(f"{last} = {index}")
            else:
                lines += [f"if {parameter.name} is not {missing}:", f"    {last} = {index}"]
    gap = False  # Whether an earlier omission can force keywords from here on.
    for index, parameter in enumerate(parameters):
        name = parameter.name
        static = name in static_names
        if parameter.kind is parameter.POSITIONAL_ONLY:
            if not static:
                lines.append(f"{args}.append({name})")
                continue
            gap = True
            value = f"{alias('defaults')}[{index}] if {name} is {missing} else {name}"
            lines += [f"if {last} >= {index}:", f"    {args}.append({value})",
                      "else:", f"    {positional} = False"]
        elif parameter.kind is parameter.POSITIONAL_OR_KEYWORD:
            inner = ""
            if static:
                lines += [f"if {name} is {missing}:", f"    {positional} = False", "else:"]
                inner = "    "
            if gap or static:
                lines += [f"{inner}if {positional}:", f"{inner}    {args}.append({name})",
                          f"{inner}else:", f"{inner}    {kwargs}[{name!r}] = {name}"]
            else:
                lines.append(f"{args}.append({name})")
            gap = gap or static
        elif parameter.kind is parameter.KEYWORD_ONLY:
            if static:
                lines += [f"if {name} is not {missing}:", f"    {kwargs}[{name!r}] = {name}"]
            else:
                lines.append(f"{kwargs}[{name!r}] = {name}")
        elif parameter.kind is parameter.VAR_POSITIONAL:
            # Native binding fills every positional slot before collecting *args.
            lines.append(f"{args}.extend({name})")
        else:
            lines.append(f"{kwargs}.update({name})")
    return [indent + line for line in lines]


def _make_wrapper(target, signature, dynamic, expose_signature, bound_values, prefixes,
                  preserve_omissions):
    parameters = list(signature.parameters.values())
    prefix = "_dda_"
    while any(p.name.startswith(prefix) for p in parameters):
        prefix = "_" + prefix
    def alias(name):
        return prefix + name
    missing = object()
    dynamic_names = {name for name, _, _ in dynamic}
    context = {alias("target"): target, alias("missing"): missing,
               alias("defaults"): tuple(p.default for p in parameters),
               alias("resolvers"): tuple(marker._resolve for _, marker, _ in dynamic),
               alias("bound"): bound_values,
               alias("prefixes"): prefixes,
               alias("StopAsyncIteration"): StopAsyncIteration,
               alias("BaseException"): BaseException}
    rendered = []
    forwarded = []
    static_defaults = {}
    for index, parameter in enumerate(parameters):
        value = parameter.default
        if value is not _EMPTY:
            if parameter.name in dynamic_names:
                value = _Source(alias("missing"))
            elif preserve_omissions:
                # Keep omission distinct from explicitly passing the static default.
                static_defaults[parameter.name] = f"{alias('defaults')}[{index}]"
                value = _Source(alias("missing"))
            else:  # An explicit signature may declare defaults the target lacks.
                value = _Source(f"{alias('defaults')}[{index}]")
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
    kind_target = _callable_target(target)
    is_asyncgen = inspect.isasyncgenfunction(kind_target)
    is_coroutine = inspect.iscoroutinefunction(kind_target)
    is_generator = inspect.isgeneratorfunction(kind_target)
    keyword = "async def" if is_coroutine or is_asyncgen else "def"
    lines = [f"{keyword} {alias('wrapper')}{definition_signature}:"]
    for index, (name, marker, dependencies) in enumerate(dynamic):
        arguments = []
        for dependency in dependencies:
            if dependency in bound_values:
                arguments.append(f"{alias('bound')}[{dependency!r}]")
            elif dependency in prefixes:
                arguments.append(f"{alias('prefixes')}[{dependency!r}] + {dependency}")
            elif dependency in static_defaults:
                # Factories can read an omitted static default without forwarding it.
                arguments.append(f"({static_defaults[dependency]} if {dependency} is "
                                 f"{alias('missing')} else {dependency})")
            else:
                arguments.append(dependency)
        lines += [f"    if {name} is {alias('missing')}:",
                  f"        {name} = {alias('resolvers')}[{index}]({', '.join(arguments)})"]
    gen = alias("gen")

    def invoke(call, indent):
        if is_asyncgen:
            return [f"{indent}{gen} = {call}"]
        if is_coroutine:
            return [f"{indent}return await {call}"]
        if is_generator:
            return [f"{indent}return (yield from {call})"]
        return [f"{indent}return {call}"]

    direct = f"{alias('target')}({', '.join(forwarded)})"
    if static_defaults:
        # Forward directly when nothing static was omitted; otherwise build the call.
        present = " and ".join(f"{name} is not {alias('missing')}" for name in static_defaults)
        lines += [f"    if {present}:", *invoke(direct, "        "), "    else:",
                  *_forwarding_lines(parameters, static_defaults, alias, "        "),
                  *invoke(f"{alias('target')}(*{alias('args')}, **{alias('kwargs')})", "        ")]
    else:
        lines += invoke(direct, "    ")
    if is_asyncgen:
        item, sent, error = map(alias, ("item", "sent", "error"))
        lines += ["    try:",
                  f"        {item} = await {gen}.__anext__()", "        while True:",
                  "            try:", f"                {sent} = yield {item}",
                  f"            except {alias('BaseException')} as {error}:",
                  f"                {item} = await {gen}.athrow({error})",
                  "            else:", f"                {item} = await {gen}.asend({sent})",
                  f"    except {alias('StopAsyncIteration')}:", "        return",
                  "    finally:", f"        await {gen}.aclose()"]
    exec(compile("\n".join(lines), "<dynamic-default-args wrapper>", "exec"), context)
    wrapper = update_wrapper(context[alias("wrapper")], target)
    if expose_signature:
        wrapper.__signature__ = signature
    return wrapper
