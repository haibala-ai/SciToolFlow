import math
e_ch = 1.602176634e-19
h_pl = 6.62607015e-34
Q_m2 = 146.6e-31
conv_a2_to_m2 = 1.0e20
spin = 2.5
obs = sorted([0.9842, 1.6209])
tol = 0.002
sites = [["site01", [[11.1103333333, 1.371, 2.652], [1.371, 3.6353333333, -3.572], [2.652, -3.572, -14.7456666667]]], ["site02", [[2.404, -0.588, -6.83], [-0.588, 10.435, 3.159], [-6.83, 3.159, -12.839]]]]
hits = []
best_id = 'none'
best_eta = 0.0
best_score = 1.0e30
for s in sites:
    name = s[0]
    A = s[1]
    S = [[(A[i][j] + A[j][i]) / 2.0 for j in range(3)] for i in range(3)]
    tr = S[0][0] + S[1][1] + S[2][2]
    T = [[S[i][j] - (tr / 3.0 if i == j else 0.0) for j in range(3)] for i in range(3)]
    tr2 = T[0][0] + T[1][1] + T[2][2]
    q0 = tr2 / 3.0
    off2 = T[0][1] * T[0][1] + T[0][2] * T[0][2] + T[1][2] * T[1][2]
    dev = (T[0][0] - q0) ** 2 + (T[1][1] - q0) ** 2 + (T[2][2] - q0) ** 2 + 2.0 * off2
    pv = math.sqrt(dev / 6.0)
    b00 = (T[0][0] - q0) / pv
    b01 = T[0][1] / pv
    b02 = T[0][2] / pv
    b10 = T[1][0] / pv
    b11 = (T[1][1] - q0) / pv
    b12 = T[1][2] / pv
    b20 = T[2][0] / pv
    b21 = T[2][1] / pv
    b22 = (T[2][2] - q0) / pv
    detB = b00 * (b11 * b22 - b12 * b21) - b01 * (b10 * b22 - b12 * b20) + b02 * (b10 * b21 - b11 * b20)
    r0 = max(-1.0, min(1.0, detB / 2.0))
    ph = math.acos(r0) / 3.0
    g1 = q0 + 2.0 * pv * math.cos(ph)
    g3 = q0 + 2.0 * pv * math.cos(ph + 2.0 * math.pi / 3.0)
    g2 = 3.0 * q0 - g1 - g3
    evs = sorted([g1, g2, g3], key=abs, reverse=True)
    Vzz = evs[0]
    Vyy = evs[1]
    Vxx = evs[2]
    eta = (Vxx - Vyy) / Vzz
    Vzz_m2 = Vzz * conv_a2_to_m2
    Cq = e_ch * Q_m2 * Vzz_m2 / h_pl / 1.0e6
    kq = Cq / (4.0 * spin * (2.0 * spin - 1.0))
    blk = [2.5, 0.5, -1.5]
    M = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    for a in range(3):
        for b in range(3):
            ma = blk[a]
            mb = blk[b]
            v = 0.0
            if a == b:
                v = 3.0 * ma * ma - spin * (spin + 1.0)
            elif mb == ma + 2.0:
                v = (eta / 2.0) * math.sqrt(spin * (spin + 1.0) - ma * (ma + 1.0)) * math.sqrt(spin * (spin + 1.0) - (ma + 1.0) * (ma + 2.0))
            elif mb == ma - 2.0:
                v = (eta / 2.0) * math.sqrt(spin * (spin + 1.0) - mb * (mb + 1.0)) * math.sqrt(spin * (spin + 1.0) - (mb + 1.0) * (mb + 2.0))
            M[a][b] = kq * v
    trM = M[0][0] + M[1][1] + M[2][2]
    qm = trM / 3.0
    offm = M[0][1] * M[0][1] + M[0][2] * M[0][2] + M[1][2] * M[1][2]
    devm = (M[0][0] - qm) ** 2 + (M[1][1] - qm) ** 2 + (M[2][2] - qm) ** 2 + 2.0 * offm
    pm = math.sqrt(devm / 6.0)
    c00 = (M[0][0] - qm) / pm
    c01 = M[0][1] / pm
    c02 = M[0][2] / pm
    c10 = M[1][0] / pm
    c11 = (M[1][1] - qm) / pm
    c12 = M[1][2] / pm
    c20 = M[2][0] / pm
    c21 = M[2][1] / pm
    c22 = (M[2][2] - qm) / pm
    detC = c00 * (c11 * c22 - c12 * c21) - c01 * (c10 * c22 - c12 * c20) + c02 * (c10 * c21 - c11 * c20)
    r1 = max(-1.0, min(1.0, detC / 2.0))
    ph2 = math.acos(r1) / 3.0
    m1 = qm + 2.0 * pm * math.cos(ph2)
    m3 = qm + 2.0 * pm * math.cos(ph2 + 2.0 * math.pi / 3.0)
    m2 = 3.0 * qm - m1 - m3
    E = sorted([m1, m2, m3])
    pred = sorted([E[1] - E[0], E[2] - E[1]])
    d0 = abs(pred[0] - obs[0])
    d1 = abs(pred[1] - obs[1])
    sc = d0 * d0 + d1 * d1
    ok = bool(d0 <= tol and d1 <= tol)
    print(name, 'symmetrized_trace_V_per_A2', tr, 'traceless_trace', tr2)
    print(name, 'principal_Vzz_Vyy_Vxx_V_per_A2', [Vzz, Vyy, Vxx])
    print(name, 'eta', eta, 'Vzz_V_per_m2', Vzz_m2, 'Cq_MHz', Cq, 'kq_MHz', kq)
    print(name, 'H_block_MHz', M)
    print(name, 'doublet_levels_MHz', E, 'predicted_pair_MHz', pred, 'observed_pair_MHz', obs)
    print(name, 'abs_residuals_MHz', [d0, d1], 'within_tolerance', ok)
    if ok:
        hits = hits + [[name, eta]]
    if sc < best_score:
        best_score = sc
        best_id = name
        best_eta = eta
print('n_matching_sites', len(hits))
if len(hits) > 0:
    print('assigned_site_id', hits[0][0])
    print('assigned_site_efg_asymmetry_eta', hits[0][1])
else:
    print('flag_no_site_within_tolerance_nearest_fit_reported')
    print('assigned_site_id', best_id)
    print('assigned_site_efg_asymmetry_eta', best_eta)
print('observed_pair_MHz', obs, 'absolute_tolerance_MHz', tol)
