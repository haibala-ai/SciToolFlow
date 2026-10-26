"""Bounded univariate polynomial roots;no physical root selection or unit inference."""
import math
import warnings
import numpy as np
from threadpoolctl import threadpool_limits


def polynomial_roots(coefficients: list) -> dict:
    """Return every complex numerical root of real descending-power coefficients.

    Args:
        coefficients: List of 2..21 finite float64-representable real numbers,
            highest power first,for degree 1..20. Leading coefficient must be
            strictly nonzero;leading zeros are not silently removed. Booleans,
            strings,complex coefficients,NaN/Inf and nested arrays are rejected.
            Trailing zeros are retained,including their zero-root multiplicity.
            Caller determines the variable's units and admissible physical roots.

    Returns:
        All degree roots as {real, imag},lexicographically sorted without
        discarding small imaginary parts or merging nearby/repeated roots.
        Parallel absolute_residuals are |p(z)| from original coefficients by
        complex float64 Horner evaluation. scaled_residuals divide |p(z)| by
        sum_i |a_i|*|z|**(degree-i);at an exact zero root with zero denominator
        the reported scaled residual is0. Also degree,coefficient_order,original
        float coefficients,root_count,method,numpy_version andlimitations.
        Uses numpy.roots companion-matrix eigenvalues on one CPU thread.
        Residuals are numerical diagnostics,not certified root enclosures or
        proofs of physical validity,accuracy,uniqueness or multiplicity.

    Raises:
        ValueError: Invalid shape/type/degree/leading zero,float64 conversion,
            eigensolver failure,nonfinite roots or any overflow/nonfinite Horner
            residual evaluation (including its absolute-value denominator).
            No partial root set or truncated polynomial is returned.
    """
    if not isinstance(coefficients,list)or not 2<=len(coefficients)<=21:
        raise ValueError('coefficients must be a list of 2..21 real numbers in descending powers')
    checked=[]
    for value in coefficients:
        if type(value)not in(int,float):
            raise ValueError('coefficients must be finite real numbers; booleans,strings and complex values are rejected')
        try:number=float(value)
        except(OverflowError,ValueError)as error:
            raise ValueError('coefficient cannot be represented as float64')from error
        if not math.isfinite(number):raise ValueError('coefficients must be finite real numbers')
        checked.append(number)
    if checked[0]==0.:raise ValueError('leading coefficient must be nonzero;leading zeros are not removed')
    degree=len(checked)-1
    try:
        with threadpool_limits(limits=1),np.errstate(all='raise'),warnings.catch_warnings():
            warnings.simplefilter('error',RuntimeWarning)
            roots=np.roots(np.asarray(checked,dtype=np.float64))
    except(FloatingPointError,OverflowError,ValueError,RuntimeWarning,np.linalg.LinAlgError)as error:
        raise ValueError('polynomial companion eigensolve failed or exceeded finite float64 arithmetic')from error
    if len(roots)!=degree or not np.all(np.isfinite(roots)):
        raise ValueError('polynomial solver did not return a complete finite root set')
    ordered=sorted([complex(z)for z in roots],key=lambda z:(z.real,z.imag));absolute=[];scaled=[]
    for z in ordered:
        magnitude=math.hypot(z.real,z.imag);value=complex(checked[0]);denominator=abs(checked[0])
        try:
            for a in checked[1:]:
                value=value*z+a;denominator=denominator*magnitude+abs(a)
                if not(math.isfinite(value.real)and math.isfinite(value.imag)and math.isfinite(denominator)):
                    raise ValueError('original-coefficient Horner residual or scaling denominator overflowed')
            residual=math.hypot(value.real,value.imag)
            if not math.isfinite(residual):raise ValueError('absolute polynomial residual overflowed')
            relative=residual/denominator if denominator else 0.
        except(OverflowError,ZeroDivisionError)as error:
            raise ValueError('original-coefficient residual evaluation failed')from error
        if not math.isfinite(relative):raise ValueError('scaled polynomial residual is nonfinite')
        absolute.append(residual);scaled.append(relative)
    return {'roots':[{'real':float(z.real),'imag':float(z.imag)}for z in ordered],
            'absolute_residuals':absolute,'scaled_residuals':scaled,'degree':degree,
            'coefficient_order':'descending powers','coefficients':checked,'root_count':degree,
            'method':'numpy.roots companion-matrix eigenvalues;original-coefficient Horner residuals',
            'numpy_version':np.__version__,
            'limitations':['Float64 numerical roots,not certified enclosures;nearby/repeated roots and badly scaled coefficients may be inaccurate even with small residuals.',
                           'All complex roots and numerical repeated entries are retained;no imaginary-part clipping,multiplicity certification or physical root selection.',
                           'Caller establishes variable/coefficient units,physical constraints and required accuracy. No pH,equilibrium or state inference.',
                           'Degree 1..20; any nonfinite numerical result oroverflow in original-coefficient residual evaluation rejects the complete call.']}
