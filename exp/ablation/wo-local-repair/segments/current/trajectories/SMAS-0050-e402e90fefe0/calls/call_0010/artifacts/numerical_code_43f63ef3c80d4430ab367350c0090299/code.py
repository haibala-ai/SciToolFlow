import numpy as np
import math
dose = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
responses = [[4.1, 1.05, 0.0, 1.02, 4.08], [6.05, 2.02, 0.0, 0.04, 2.01], [-1.95, 0.01, 1.02, 1.04, 0.03]]
targets = [1.0, 1.0, -1.0]
coefs = [np.polyfit(dose, np.array(responses[i]), 2) for i in range(3)]
turns = [-float(coefs[i][1]) / (2.0 * float(coefs[i][0])) for i in range(3)]
supports = []
for i in range(3):
    a = float(coefs[i][0])
    b = float(coefs[i][1])
    c = float(coefs[i][2]) - targets[i]
    disc = b * b - 4.0 * a * c
    if disc >= 0.0:
        sd = math.sqrt(disc)
        rr = sorted([(-b - sd) / (2.0 * a), (-b + sd) / (2.0 * a)])
        roots = [{"real": float(rr[0]), "imag": 0.0}, {"real": float(rr[1]), "imag": 0.0}]
    else:
        re = -b / (2.0 * a)
        im = math.sqrt(-disc) / abs(2.0 * a)
        roots = [{"real": float(re), "imag": -float(im)}, {"real": float(re), "imag": float(im)}]
    keep = [r for r in roots if abs(r["imag"]) <= 1e-8 and r["real"] >= -2.0 and r["real"] <= 2.0]
    supports = supports + [keep]
print("coefficients_a", coefs[0].tolist())
print("coefficients_b", coefs[1].tolist())
print("coefficients_c", coefs[2].tolist())
print("turning_a", turns[0])
print("turning_b", turns[1])
print("turning_c", turns[2])
print("supported_roots_a", supports[0])
print("supported_roots_b", supports[1])
print("supported_roots_c", supports[2])
