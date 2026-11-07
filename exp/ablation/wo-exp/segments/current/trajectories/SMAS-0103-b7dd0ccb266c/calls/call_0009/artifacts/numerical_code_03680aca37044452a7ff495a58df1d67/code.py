import math
ids = ['lambda-A', 'lambda-B', 'lambda-C']
mats = [
 [[1.0, 2.0], [2.0, 4.0], [1.0, 2.0]],
 [[1.0, 2.0], [2.0, 4.0], [3.0, 1.0]],
 [[1.0, 2.0], [2.0, 4.0], [0.1, 3.0]]
]
mins = [0.0, 0.0, 0.0]
for i in range(len(mats)):
    a = mats[i]
    g00 = 0.0
    g01 = 0.0
    g11 = 0.0
    for row in a:
        g00 = g00 + row[0] * row[0]
        g01 = g01 + row[0] * row[1]
        g11 = g11 + row[1] * row[1]
    tr = g00 + g11
    det = g00 * g11 - g01 * g01
    disc = math.sqrt(tr * tr - 4.0 * det)
    lam = (tr - disc) / 2.0
    if lam < 0.0 and lam > -1e-12:
        lam = 0.0
    mins[i] = math.sqrt(lam)
best = max(mins)
sel = 0
for i in range(len(mins)):
    if mins[i] >= best - 1e-8:
        sel = i
        break
orig = [[1.0, 2.0], [2.0, 4.0]]
g00 = 0.0
g01 = 0.0
g11 = 0.0
for row in orig:
    g00 = g00 + row[0] * row[0]
    g01 = g01 + row[0] * row[1]
    g11 = g11 + row[1] * row[1]
tr = g00 + g11
det = g00 * g11 - g01 * g01
disc = math.sqrt(tr * tr - 4.0 * det)
lam = (tr - disc) / 2.0
if lam < 0.0 and lam > -1e-12:
    lam = 0.0
orig_min = math.sqrt(lam)
ident = 'false'
if orig_min > 1e-8:
    ident = 'true'
print('minimum_singular_values_by_channel=' + str(mins))
print('original_two_row_min_singular_value=' + str(orig_min))
print('{"selected_channel_id":"' + ids[sel] + '","minimum_singular_value":' + str(mins[sel]) + ',"original_channels_identifiable":' + ident + '}')