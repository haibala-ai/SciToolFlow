edges = [{'edge_id': '0:1:-1,-1,0', 'center_index': 0, 'neighbor_index': 1, 'image_shift': [-1, -1, 0], 'distance_angstrom': 3.6878177829171546, 'displacement_angstrom': [-2.8, -2.4, -8.881784197001252e-16]}, {'edge_id': '0:1:-1,0,0', 'center_index': 0, 'neighbor_index': 1, 'image_shift': [-1, 0, 0], 'distance_angstrom': 3.2249030993194197, 'displacement_angstrom': [-2.8, 1.6, 0.0]}, {'edge_id': '0:1:0,-1,0', 'center_index': 0, 'neighbor_index': 1, 'image_shift': [0, -1, 0], 'distance_angstrom': 2.6832815729997477, 'displacement_angstrom': [1.2000000000000002, -2.4, 0.0]}, {'edge_id': '0:1:0,0,0', 'center_index': 0, 'neighbor_index': 1, 'image_shift': [0, 0, 0], 'distance_angstrom': 2.0, 'displacement_angstrom': [1.2, 1.6, 0.0]}, {'edge_id': '1:0:0,0,0', 'center_index': 1, 'neighbor_index': 0, 'image_shift': [0, 0, 0], 'distance_angstrom': 2.0, 'displacement_angstrom': [-1.2, -1.6, 0.0]}, {'edge_id': '1:0:0,1,0', 'center_index': 1, 'neighbor_index': 0, 'image_shift': [0, 1, 0], 'distance_angstrom': 2.6832815729997477, 'displacement_angstrom': [-1.2000000000000002, 2.4, 0.0]}, {'edge_id': '1:0:1,0,0', 'center_index': 1, 'neighbor_index': 0, 'image_shift': [1, 0, 0], 'distance_angstrom': 3.2249030993194197, 'displacement_angstrom': [2.8, -1.6, 0.0]}, {'edge_id': '1:0:1,1,0', 'center_index': 1, 'neighbor_index': 0, 'image_shift': [1, 1, 0], 'distance_angstrom': 3.6878177829171546, 'displacement_angstrom': [2.8, 2.4, 8.881784197001252e-16]}]
cell = [[4.0, 0.0, 2.4492935982947064e-16], [-2.4492935982947064e-16, 4.0, 2.4492935982947064e-16], [0.0, 0.0, 10.0]]
k = 1.0
import math
edges = edges
cell = cell
k = k
keys = []
bars = []
for e in edges:
    i = e['center_index']
    j = e['neighbor_index']
    s = e['image_shift']
    d = e['displacement_angstrom']
    if i == 0 and j == 1:
        key = (0, 1, s[0], s[1], s[2])
        a = 0
        b = 1
        r = [d[0], d[1], d[2]]
    elif i == 1 and j == 0:
        key = (0, 1, -s[0], -s[1], -s[2])
        a = 0
        b = 1
        r = [-d[0], -d[1], -d[2]]
    else:
        if i == j:
            sign = 1
            if s[0] < 0:
                sign = -1
            elif s[0] == 0 and s[1] < 0:
                sign = -1
            elif s[0] == 0 and s[1] == 0 and s[2] < 0:
                sign = -1
            key = (i, j, sign*s[0], sign*s[1], sign*s[2])
            a = i
            b = j
            r = [sign*d[0], sign*d[1], sign*d[2]]
        else:
            if i < j:
                key = (i, j, s[0], s[1], s[2])
                a = i
                b = j
                r = [d[0], d[1], d[2]]
            else:
                key = (j, i, -s[0], -s[1], -s[2])
                a = j
                b = i
                r = [-d[0], -d[1], -d[2]]
    if key not in keys:
        keys = keys + [key]
        bars = bars + [[a, b, r[0], r[1], r[2]]]
B = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
A = [[0.0, 0.0], [0.0, 0.0]]
M = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
for bar in bars:
    a = bar[0]
    b = bar[1]
    rx = bar[2]
    ry = bar[3]
    rz = bar[4]
    L = math.sqrt(rx*rx + ry*ry + rz*rz)
    q = [rx*rx/L, ry*ry/L, math.sqrt(2.0)*rx*ry/L]
    if a == 0 and b == 1:
        gx = rx/L
        gy = ry/L
    elif a == 1 and b == 0:
        gx = -rx/L
        gy = -ry/L
    else:
        gx = 0.0
        gy = 0.0
    for p in range(3):
        for t in range(3):
            B[p][t] = B[p][t] + q[p]*q[t]
    A[0][0] = A[0][0] + gx*gx
    A[0][1] = A[0][1] + gx*gy
    A[1][0] = A[1][0] + gy*gx
    A[1][1] = A[1][1] + gy*gy
    for p in range(3):
        M[0][p] = M[0][p] + gx*q[p]
        M[1][p] = M[1][p] + gy*q[p]
v1 = cell[0]
v2 = cell[1]
area = abs(v1[0]*v2[1] - v1[1]*v2[0])
C_aff = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
C_rel = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
for p in range(3):
    for t in range(3):
        C_aff[p][t] = k*B[p][t]/area
        C_rel[p][t] = k*B[p][t]/area
detA = A[0][0]*A[1][1] - A[0][1]*A[1][0]
if abs(detA) > 1e-12:
    Ai = [[A[1][1]/detA, -A[0][1]/detA], [-A[1][0]/detA, A[0][0]/detA]]
    for p in range(3):
        for t in range(3):
            val = 0.0
            for i2 in range(2):
                for j2 in range(2):
                    val = val + M[i2][p]*Ai[i2][j2]*M[j2][t]
            C_rel[p][t] = k*(B[p][t] - val)/area
print('[' + str(C_aff) + ', ' + str(C_rel) + ', ' + str(len(bars)) + ', ' + str(bars) + ', ' + str(area) + ', ' + str(detA) + ']')