import numpy as np
import math

dose = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
responses = [[4.1, 1.05, 0.0, 1.02, 4.08], [6.05, 2.02, 0.0, 0.04, 2.01], [-1.95, 0.01, 1.02, 1.04, 0.03]]
targets = [1.0, 1.0, -1.0]
labels = ['a', 'b', 'c']
fields = []
for i in range(3):
    y = np.array(responses[i])
    coef = np.polyfit(dose, y, 2).tolist()
    c0 = coef[0]
    c1 = coef[1]
    c2 = coef[2]
    t = targets[i]
    a = c0
    b = c1
    c = c2 - t
    D = b * b - 4.0 * a * c
    if D >= 0.0:
        s = math.sqrt(D)
        r1 = (-b - s) / (2.0 * a)
        r2 = (-b + s) / (2.0 * a)
        roots = [[r1, 0.0], [r2, 0.0]]
    else:
        s = math.sqrt(-D)
        re = -b / (2.0 * a)
        im = s / (2.0 * a)
        roots = [[re, -im], [re, im]]
    roots = sorted(roots)
    resids = []
    supp = []
    for j in range(len(roots)):
        x = roots[j][0]
        yv = roots[j][1]
        pr = a * (x * x - yv * yv) + b * x + c
        pi = a * (2.0 * x * yv) + b * yv
        resids = resids + [math.sqrt(pr * pr + pi * pi)]
        if abs(yv) <= 1e-8 and x >= -2.0 and x <= 2.0:
            supp = supp + [[x, yv]]
    turn = -b / (2.0 * a)
    roots_str = '['
    for j in range(len(roots)):
        if j > 0:
            roots_str = roots_str + ','
        roots_str = roots_str + '{"real":' + str(roots[j][0]) + ',"imag":' + str(roots[j][1]) + '}'
    roots_str = roots_str + ']'
    supp_str = '['
    for j in range(len(supp)):
        if j > 0:
            supp_str = supp_str + ','
        supp_str = supp_str + '{"real":' + str(supp[j][0]) + ',"imag":' + str(supp[j][1]) + '}'
    supp_str = supp_str + ']'
    lab = labels[i]
    fields = fields + ['"coefficients_' + lab + '": ' + str(coef)]
    fields = fields + ['"roots_' + lab + '": ' + roots_str]
    fields = fields + ['"turning_' + lab + '": ' + str(turn)]
    fields = fields + ['"root_residuals_' + lab + '": ' + str(resids)]
    fields = fields + ['"supported_roots_' + lab + '": ' + supp_str]
print('{')
for i in range(len(fields)):
    if i > 0:
        print(',')
    print(fields[i])
print('}')
