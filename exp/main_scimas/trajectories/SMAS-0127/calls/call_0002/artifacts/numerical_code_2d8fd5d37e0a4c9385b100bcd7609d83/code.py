site_order = ['A', 'B1', 'B2']
site_elements = ['Fe', 'Fe', 'Fe']
allowed = [2, 3]
n_Fe = 3
n_O = 4
oxygen_valence = -2
mu = {2: 4.0, 3: 5.0}
target_moment = 4.0

target_charge = -oxygen_valence * n_O
print('site_order_used', site_order)
print('site_elements_used', site_elements)
print('allowed_valences_used', allowed)
print('n_Fe_n_O_oxygen_valence', n_Fe, n_O, oxygen_valence)
print('moment_map_used', mu)
print('net_moment_target_muB', target_moment)
print('charge_target_from_neutrality', target_charge)

vectors = [[]]
for i in range(len(site_order)):
    grown = []
    for v in vectors:
        for val in allowed:
            grown = grown + [v + [val]]
    vectors = grown
print('enumerated_vector_count', len(vectors))

neutral = []
for c in vectors:
    if len(c) == n_Fe and sum(c) == target_charge:
        neutral = neutral + [c]
print('neutral_vector_count', len(neutral))
print('neutral_vectors', neutral)

lo = min(allowed)
hi = max(allowed)
n_hi = (target_charge - lo * n_Fe) / (hi - lo)
n_lo = n_Fe - n_hi
print('Fe_II_and_Fe_III_counts_per_formula_unit', [n_lo, n_hi])

retained = []
for c in neutral:
    mA = mu[c[0]]
    mB = 0.0
    for k in range(1, len(c)):
        mB = mB + mu[c[k]]
    net = abs(mA - mB)
    print('candidate', c, 'A_moment_muB', mA, 'B_moment_sum_muB', mB, 'net_moment_muB', net)
    if abs(net - target_moment) < 1e-9:
        retained = retained + [c]
print('retained_count', len(retained))
print('retained_site_valence_assignments', retained)
print('retained_in_site_order', site_order, retained)

all_id = True
if len(retained) > 0:
    for j in range(len(site_order)):
        for r in retained:
            if r[j] != retained[0][j]:
                all_id = False
print('all_labelled_site_valences_identified', all_id)
