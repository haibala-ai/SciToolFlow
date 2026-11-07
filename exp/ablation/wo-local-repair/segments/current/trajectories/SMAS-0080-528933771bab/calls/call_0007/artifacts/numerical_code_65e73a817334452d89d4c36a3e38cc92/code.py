import math
data = [[1, 2, 2, 3, 2, 1, 3], [-2, 5, -1, 6, 0, 4, -1], [0.1, 0.2, 0.15, 0.05, 0.3, 0.1, 0.2]]
for i in range(3):
    xs = data[i]
    n = len(xs)
    m = sum(xs) / n
    ss = sum((x - m) * (x - m) for x in xs)
    sd = math.sqrt(ss / (n - 1))
    z = m / sd
    x = z / math.sqrt(2.0)
    sign = 1.0
    if x < 0.0:
        sign = -1.0
        x = -x
    t = 1.0 / (1.0 + 0.3275911 * x)
    poly = (((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t)
    erf_abs = 1.0 - poly * math.exp(-x * x)
    erf_x = sign * erf_abs
    ppos = 0.5 * (1.0 + erf_x)
    p4 = 5.0 * (ppos ** 4) * (1.0 - ppos) + ppos ** 5
    print(i, m, sd, ppos, p4)
