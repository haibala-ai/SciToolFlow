import math
import numpy as np
dose = [-2, -1, 0, 1, 2]
responses = [[4.1, 1.05, 0, 1.02, 4.08], [6.05, 2.02, 0, 0.04, 2.01], [-1.95, 0.01, 1.02, 1.04, 0.03]]
targets = [1, 1, -1]
letters = ['a', 'b', 'c']
out = {}
for i in range(3):
    coeffs = np.polyfit(dose, responses[i], 2)
    a = float(coeffs[0])
    b = float(coeffs[1])
    c = float(coeffs[2]) - targets[i]
    disc = b*b - 4*a*c
    if disc >= 0:
        r1 = (-b + math.sqrt(disc))/(2*a)
        r2 = (-b - math.sqrt(disc))/(2*a)
        roots = [(r1, 0.0), (r2, 0.0)]
    else:
        real = -b/(2*a)
        imag = math.sqrt(-disc)/(2*a)
        roots = [(real, imag), (real, -imag)]
    roots = sorted(roots)
    roots_dict = [{'real': float(roots[0][0]), 'imag': float(roots[0][1])}, {'real': float(roots[1][0]), 'imag': float(roots[1][1])}]
    res0_real = a*(roots[0][0]**2 - roots[0][1]**2) + b*roots[0][0] + c
    res0_imag = a*(2*roots[0][0]*roots[0][1]) + b*roots[0][1]
    res0 = float(math.sqrt(res0_real**2 + res0_imag**2))
    res1_real = a*(roots[1][0]**2 - roots[1][1]**2) + b*roots[1][0] + c
    res1_imag = a*(2*roots[1][0]*roots[1][1]) + b*roots[1][1]
    res1 = float(math.sqrt(res1_real**2 + res1_imag**2))
    turning = float(-b/(2*a))
    supported = [r for r in roots_dict if abs(r['imag']) <= 1e-8 and r['real'] >= -2 and r['real'] <= 2]
    out['coefficients_' + letters[i]] = coeffs.tolist()
    out['roots_' + letters[i]] = roots_dict
    out['turning_' + letters[i]] = turning
    out['root_residuals_' + letters[i]] = [res0, res1]
    out['supported_roots_' + letters[i]] = supported
print(out)