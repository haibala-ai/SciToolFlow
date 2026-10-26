import functools
import shlex
import inspect
import json
import re
import math


class InputValidationError(ValueError):
    """The supplied arguments do not satisfy the callable's input contract."""


def parse_parameters(
    func, value, *, coerce_scalar_strings=True, coerce_integral_floats=False
):
    try:
        return _parse_parameters(
            func,
            value,
            coerce_scalar_strings=coerce_scalar_strings,
            coerce_integral_floats=coerce_integral_floats,
        )
    except InputValidationError:
        raise
    except (TypeError, ValueError) as error:
        raise InputValidationError(str(error)) from error


def _normalise_key(name):
    """Compare parameter names ignoring case and separators.

    The registry mixes ``PDB_id``, ``PDB_name``, ``pdb_id`` and ``material_id`` for the
    same concept, so a name that differs only in case or underscores is treated as the
    same parameter.
    """
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def _parse_parameters(
    func, value, *, coerce_scalar_strings=True, coerce_integral_floats=False
):
    """Bind JSON or legacy named arguments without splitting a bare molecule/sequence."""
    signature = inspect.signature(func)
    names = set(signature.parameters)
    args, kwargs = [], {}
    decoded = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(decoded, dict):
        # Parameter names in this pool are inconsistently cased (PDB_id, PDB_name, pdb_id,
        # material_id). A caller that names the right concept with different capitalisation
        # or underscores is bound to the declared parameter instead of failing the call,
        # as long as the mapping is unambiguous.
        normalised = {}
        for name in names:
            normalised.setdefault(_normalise_key(name), name)
        kwargs = {}
        for key, entry in decoded.items():
            if key in names:
                kwargs[key] = entry
                continue
            target = normalised.get(_normalise_key(key))
            if target is not None and target not in kwargs:
                kwargs[target] = entry
            else:
                kwargs[key] = entry
    elif isinstance(decoded, list):
        args = decoded if len(names) > 1 else [decoded]
    elif (
        isinstance(value, str)
        and re.match(r"^\s*([A-Za-z_]\w*)\s*=", value)
        and re.match(r"^\s*([A-Za-z_]\w*)\s*=", value).group(1) in names
    ):
        lexer = shlex.shlex(value, posix=True)
        lexer.whitespace = ", \t\n"
        lexer.whitespace_split = True
        for token in lexer:
            key, entry = token.split("=", 1)
            kwargs[key] = entry
    else:
        required = [
            p
            for p in signature.parameters.values()
            if p.default is inspect.Parameter.empty
        ]
        if len(required) > 1 and isinstance(value, str):
            lexer = shlex.shlex(value, posix=True)
            lexer.whitespace = ", \t\n"
            lexer.whitespace_split = True
            args = list(lexer)
        else:
            # A bare numeric identifier is still text for a string parameter.
            first = next(iter(signature.parameters.values()), None)
            text_parameter = first and first.annotation in (str, "str")
            args = [
                (
                    value
                    if text_parameter
                    and isinstance(value, str)
                    and not isinstance(decoded, str)
                    else decoded
                )
            ]
    try:
        bound = signature.bind(*args, **kwargs)
    except TypeError as error:
        raise InputValidationError(str(error)) from error
    for name, entry in bound.arguments.items():
        parameter = signature.parameters[name]
        kind = parameter.annotation
        if (
            kind is inspect.Parameter.empty
            and parameter.default is not inspect.Parameter.empty
        ):
            kind = type(parameter.default)
        if coerce_scalar_strings and isinstance(entry, str):
            try:
                if kind in (int, "int"):
                    entry = int(entry)
                elif kind in (float, "float"):
                    entry = float(entry)
                elif kind in (bool, "bool"):
                    if entry.lower() not in ("true", "false", "1", "0"):
                        raise ValueError("expected true or false")
                    entry = entry.lower() in ("true", "1")
            except ValueError as error:
                raise InputValidationError(f"{name}: expected {kind}") from error
        if (
            coerce_integral_floats
            and kind in (int, "int")
            and type(entry) is float
            and math.isfinite(entry)
            and entry.is_integer()
        ):
            # JSON numbers such as 448.0 are already exact integer values.
            # Do not round fractional counts or parse strings implicitly.
            entry = int(entry)
        if entry is None and parameter.default is None:
            continue
        expected = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "list[str]": list,
        }.get(kind, kind)
        if expected in (str, int, float, bool, list):
            valid = (
                isinstance(entry, (int, float)) and not isinstance(entry, bool)
                if expected is float
                else isinstance(entry, expected)
            )
            if expected is int and isinstance(entry, bool):
                valid = False
            if not valid or (
                kind == "list[str]" and any(not isinstance(item, str) for item in entry)
            ):
                raise InputValidationError(f"{name}: expected {kind}")
            if expected is float and not math.isfinite(entry):
                raise InputValidationError(f"{name}: expected a finite number")
        # A required text argument that is empty or whitespace can only produce a
        # meaningless "successful" result, so reject it before the tool runs.
        if (
            parameter.default is inspect.Parameter.empty
            and parameter.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and isinstance(entry, str)
            and not entry.strip()
        ):
            raise InputValidationError(
                f"{name}: a required text argument must not be empty"
            )
        bound.arguments[name] = entry
    return bound.args, bound.kwargs


def param_decorator(func):
    @functools.wraps(func)
    def wrapper(param_string):
        args, kwargs = parse_parameters(func, param_string)
        return func(*args, **kwargs)

    return wrapper


def param_decorator_download_paper(func):
    @functools.wraps(func)
    def wrapper(param_string):
        params = {}
        args = []

        param_split = shlex.split(param_string)

        for param in param_split:
            if "=" in param:
                key, value = param.split("=")
                try:
                    value = int(value)
                except ValueError:
                    pass
                params[key.strip()] = value
            else:
                args.append(param.strip())

        return func(*args, **params)

    return wrapper
