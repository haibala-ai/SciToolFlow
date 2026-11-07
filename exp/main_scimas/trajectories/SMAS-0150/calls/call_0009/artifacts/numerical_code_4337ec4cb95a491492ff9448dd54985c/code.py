import numpy as np
V1 = np.array([14.8, 15.4, 16.0, 16.6, 17.2])
E1 = np.array([-4.966295850997912, -4.991573962749478, -5.0, -4.991573962749478, -4.966295850997912])
V2 = np.array([13.6, 14.3, 15.0, 15.7, 16.4])
E2 = np.array([-4.913299926642171, -4.940824981660543, -4.95, -4.940824981660543, -4.913299926642171])
CONV = 160.2176634
p_lo = 0.0
p_hi = 8.0 / CONV
c1 = np.polyfit(V1, E1, 2)
c2 = np.polyfit(V2, E2, 2)
a1, b1, d1 = float(c1[0]), float(c1[1]), float(c1[2])
a2, b2, d2 = float(c2[0]), float(c2[1]), float(c2[2])
res1 = float(np.max(np.abs(np.polyval(c1, V1) - E1)))
res2 = float(np.max(np.abs(np.polyval(c2, V2) - E2)))
vmin1, vmax1 = float(np.min(V1)), float(np.max(V1))
vmin2, vmax2 = float(np.min(V2)), float(np.max(V2))
A = a1 - a2
B = 2.0 * (a1 * b2 - a2 * b1)
C = a1 * b2 * b2 - a2 * b1 * b1 + 4.0 * a1 * a2 * (d1 - d2)
sq = np.sqrt(B * B - 4.0 * A * C)
r1 = (-B + sq) / (2.0 * A)
r2 = (-B - sq) / (2.0 * A)
eps = 1e-9
cands = []
for r in (r1, r2):
    rr = float(r)
    if p_lo <= rr <= p_hi:
        qm = (d1 - d2) - (b1 + rr - eps) ** 2 / (4.0 * a1) + (b2 + rr - eps) ** 2 / (4.0 * a2)
        qp = (d1 - d2) - (b1 + rr + eps) ** 2 / (4.0 * a1) + (b2 + rr + eps) ** 2 / (4.0 * a2)
        if qm * qp < 0.0:
            cands = cands + [rr]
cands = sorted(cands)
p_star = cands[0] if len(cands) == 1 else p_lo
p_below = 0.5 * (p_lo + p_star)
p_above = 0.5 * (p_star + p_hi)
q_below = (d1 - d2) - (b1 + p_below) ** 2 / (4.0 * a1) + (b2 + p_below) ** 2 / (4.0 * a2)
q_above = (d1 - d2) - (b1 + p_above) ** 2 / (4.0 * a1) + (b2 + p_above) ** 2 / (4.0 * a2)
below = 'phase01' if q_below < 0.0 else 'phase02'
above = 'phase01' if q_above < 0.0 else 'phase02'
v1_star = -(b1 + p_star) / (2.0 * a1)
v2_star = -(b2 + p_star) / (2.0 * a2)
v_low = v1_star if below == 'phase01' else v2_star
v_high = v1_star if above == 'phase01' else v2_star
rel = (v_high - v_low) / v_low
v1_lo = -(b1 + p_lo) / (2.0 * a1)
v1_hi = -(b1 + p_hi) / (2.0 * a1)
v2_lo = -(b2 + p_lo) / (2.0 * a2)
v2_hi = -(b2 + p_hi) / (2.0 * a2)
ok1_lo = v1_lo >= vmin1 and v1_lo <= vmax1
ok1_star = v1_star >= vmin1 and v1_star <= vmax1
ok1_hi = v1_hi >= vmin1 and v1_hi <= vmax1
ok2_lo = v2_lo >= vmin2 and v2_lo <= vmax2
ok2_star = v2_star >= vmin2 and v2_star <= vmax2
ok2_hi = v2_hi >= vmin2 and v2_hi <= vmax2
out = (
    '{'
    f'"phase_below_transition_id": "{below}", '
    f'"phase_above_transition_id": "{above}", '
    f'"transition_pressure_gpa": {p_star * CONV:.10f}, '
    f'"relative_volume_jump_high_minus_low": {rel:.12f}, '
    f'"crossover_root_count": {len(cands)}, '
    f'"max_abs_quadratic_residual_ev_per_atom_phase01": {res1:.3e}, '
    f'"max_abs_quadratic_residual_ev_per_atom_phase02": {res2:.3e}, '
    f'"phase01_support_angstrom3": [{vmin1:.10f}, {vmax1:.10f}], '
    f'"phase02_support_angstrom3": [{vmin2:.10f}, {vmax2:.10f}], '
    f'"phase01_volume_at_low_end": {v1_lo:.10f}, '
    f'"phase01_volume_at_transition": {v1_star:.10f}, '
    f'"phase01_volume_at_high_end": {v1_hi:.10f}, '
    f'"phase02_volume_at_low_end": {v2_lo:.10f}, '
    f'"phase02_volume_at_transition": {v2_star:.10f}, '
    f'"phase02_volume_at_high_end": {v2_hi:.10f}, '
    f'"phase01_inside_support_at_low_end": {"true" if ok1_lo else "false"}, '
    f'"phase01_inside_support_at_transition": {"true" if ok1_star else "false"}, '
    f'"phase01_inside_support_at_high_end": {"true" if ok1_hi else "false"}, '
    f'"phase02_inside_support_at_low_end": {"true" if ok2_lo else "false"}, '
    f'"phase02_inside_support_at_transition": {"true" if ok2_star else "false"}, '
    f'"phase02_inside_support_at_high_end": {"true" if ok2_hi else "false"}'
    '}'
)
print(out)
