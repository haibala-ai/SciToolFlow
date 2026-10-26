"""Decode a bounded, closed arithmetic expression used in calculator evidence.

This is a small data grammar, not Python/Wolfram execution or a general CAS.
Supported: finite decimal/scientific literals, + - * / ^, parentheses, Log/Exp/
Sqrt (or lowercase names), flat scalar lists or comma-separated scalar results,
and a presentation-only outer N[expression, digits] with digits 1..17.
Every intermediate uses ordinary float64 arithmetic. No variables, strings,
attributes, assignments, units, symbolic manipulation or external calls exist.
"""

import math
import re


class NumericExpressionError(ValueError):
    pass


TOKEN = re.compile(
    r"\s*((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z]+|[+*/^(),{}\[\]-])",
    re.ASCII,
)


def decode_numeric_expression(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 10000:
        raise NumericExpressionError(
            "Expected 1..10000 characters of closed arithmetic"
        )
    tokens = []
    pos = 0
    text = text.strip()
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if m is None:
            raise NumericExpressionError("Unsupported calculator syntax")
        tokens.append(m.group(1))
        pos = m.end()
        if len(tokens) > 1000:
            raise NumericExpressionError("Calculator expression exceeds 1000 tokens")
    cursor = 0
    depth = 0

    def peek():
        return tokens[cursor] if cursor < len(tokens) else None

    def take(want=None):
        nonlocal cursor
        t = peek()
        if t is None or (want is not None and t != want):
            raise NumericExpressionError("Incomplete calculator expression")
        cursor += 1
        return t

    def finite(v):
        if type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e300:
            raise NumericExpressionError(
                "Calculator values must be finite bounded scalars"
            )
        return float(v)

    def scalar(v):
        if isinstance(v, list):
            raise NumericExpressionError("Arithmetic operands must be scalars")
        return finite(v)

    def expression():
        nonlocal depth
        depth += 1
        if depth > 32:
            raise NumericExpressionError("Calculator nesting exceeds 32 levels")
        v = term()
        while peek() in ("+", "-"):
            operation = take()
            rhs = scalar(term())
            lhs = scalar(v)
            v = finite(lhs + rhs if operation == "+" else lhs - rhs)
        depth -= 1
        return v

    def term():
        v = unary()
        while peek() in ("*", "/"):
            operation = take()
            rhs = scalar(unary())
            lhs = scalar(v)
            if operation == "/" and rhs == 0:
                raise NumericExpressionError("Zero calculator denominator")
            v = finite(lhs * rhs if operation == "*" else lhs / rhs)
            if v == 0 and lhs != 0 and (operation == "/" or rhs != 0):
                raise NumericExpressionError("Calculator arithmetic underflow")
        return v

    def unary():
        # Count a unary/power chain as depth too; the token limit alone does not
        # prevent Python recursion overflow on an adversarial string.
        nonlocal depth
        depth += 1
        if depth > 32:
            raise NumericExpressionError("Calculator nesting exceeds 32 levels")
        if peek() in ("+", "-"):
            sign = take()
            v = scalar(unary())
            v = v if sign == "+" else -v
        else:
            v = atom()
            if peek() == "^":
                take("^")
                exponent = scalar(unary())
                base = scalar(v)
                if abs(exponent) > 100:
                    raise NumericExpressionError("Calculator exponent exceeds 100")
                try:
                    v = finite(base**exponent)
                    if v == 0 and base != 0:
                        raise NumericExpressionError("Calculator power underflow")
                except (OverflowError, ZeroDivisionError, TypeError):
                    raise NumericExpressionError(
                        "Invalid real calculator power"
                    ) from None
        depth -= 1
        return v

    def sequence(close):
        vals = [scalar(expression())]
        while peek() == ",":
            take(",")
            vals.append(scalar(expression()))
            if len(vals) > 100:
                raise NumericExpressionError("Calculator list exceeds 100 scalars")
        take(close)
        return vals

    def atom():
        token = take()
        if token == "(":
            v = expression()
            take(")")
            return v
        if token in ("{", "["):
            return sequence("}" if token == "{" else "]")
        if token in ("Log", "Exp", "Sqrt", "log", "exp", "sqrt"):
            opening = take()
            if opening not in ("[", "("):
                raise NumericExpressionError("Function requires brackets")
            v = scalar(expression())
            take("]" if opening == "[" else ")")
            try:
                value = finite(
                    {"log": math.log, "exp": math.exp, "sqrt": math.sqrt}[
                        token.lower()
                    ](v)
                )
                if token.lower() == "exp" and value == 0:
                    raise NumericExpressionError("Calculator exponential underflow")
                return value
            except (ValueError, OverflowError):
                raise NumericExpressionError(
                    "Invalid calculator function domain"
                ) from None
        if token == "N":
            # This wrapper only declares displayed float64 precision. It does
            # not request arbitrary precision or change inner arithmetic.
            if cursor != 1:
                raise NumericExpressionError(
                    "N is allowed only at the outermost position"
                )
            take("[")
            v = expression()
            if peek() == ",":
                take(",")
                digits = take()
                if not digits.isdigit() or not 1 <= int(digits) <= 17:
                    raise NumericExpressionError("N presentation digits must be 1..17")
            take("]")
            return v
        if (
            not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", token)
            or len(token) > 64
        ):
            raise NumericExpressionError("Expected a finite numeric literal")
        return finite(float(token))

    if not tokens:
        raise NumericExpressionError("Empty calculator expression")
    result = expression()
    if peek() == ",":
        result = [scalar(result)]
        while peek() == ",":
            take(",")
            result.append(scalar(expression()))
            if len(result) > 100:
                raise NumericExpressionError("Calculator list exceeds 100 scalars")
    if cursor != len(tokens):
        raise NumericExpressionError("Trailing calculator syntax")
    return result
