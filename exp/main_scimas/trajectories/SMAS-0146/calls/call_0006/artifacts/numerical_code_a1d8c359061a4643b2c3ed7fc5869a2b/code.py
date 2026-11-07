records = [{'record_id': 'entry01', 'source_material_id': 'mp-aaaaadeb', 'formula': 'ZnO', 'structure_file': 'local_model_structure_1.cif', 'structure_sha256': '0988e26a382eb096c41557997b62b3dfd9073cacd5f802eb9544be444607ff70', 'cation': 'Zn', 'cation_formal_valence': 2.0, 'oxygen_formal_valence_magnitude': 2.0, 'cation_oxygen_R0_angstrom': 1.684, 'cation_oxygen_B_angstrom': 0.383, 'declared_heteronuclear_cutoff_angstrom': 2.5}, {'record_id': 'entry02', 'source_material_id': 'mp-aaaaadyf', 'formula': 'TiO2', 'structure_file': 'local_model_structure_2.cif', 'structure_sha256': '1e610eed945d43ec046a0a4ded703eaefba7b8968730f67f15321b4a123bf633', 'cation': 'Ti', 'cation_formal_valence': 4.0, 'oxygen_formal_valence_magnitude': 2.0, 'cation_oxygen_R0_angstrom': 1.819, 'cation_oxygen_B_angstrom': 0.342, 'declared_heteronuclear_cutoff_angstrom': 2.5}]
m1 = [[1.9798223456605797, 0.0, 2.0], [1.972789306860527, 0.0, 3.0], [1.972794516238995, 0.0, 3.0], [1.9727894764300387, 0.0, 3.0], [1.972789476430039, 1.0, 2.0], [1.9727945162389946, 1.0, 2.0], [1.9727893068605273, 1.0, 2.0], [1.9798223456605797, 1.0, 3.0], [1.9798223456605797, 2.0, 0.0], [1.972789306860527, 2.0, 1.0], [1.972794516238995, 2.0, 1.0], [1.9727894764300387, 2.0, 1.0], [1.9727894764300389, 3.0, 0.0], [1.9727945162389944, 3.0, 0.0], [1.9727893068605271, 3.0, 0.0], [1.97982234566058, 3.0, 1.0]]
sp1 = ['Zn', 'Zn', 'O', 'O']
m2 = [[1.950389047022045, 0.0, 4.0], [1.950441473264771, 0.0, 6.0], [1.9798389506011282, 0.0, 8.0], [1.9798343778296044, 0.0, 9.0], [1.9531797042073875, 0.0, 10.0], [1.953131028751234, 0.0, 11.0], [1.9531512374930222, 1.0, 4.0], [1.9798355243821464, 1.0, 5.0], [1.9531610089559108, 1.0, 6.0], [1.9798344020549188, 1.0, 7.0], [1.950420549820999, 1.0, 10.0], [1.9504049525675533, 1.0, 11.0], [1.9795974886856968, 2.0, 4.0], [1.951757799436511, 2.0, 5.0], [1.9517600845630647, 2.0, 7.0], [1.9517712547082366, 2.0, 8.0], [1.9517677955041268, 2.0, 9.0], [1.9795975276683206, 2.0, 11.0], [1.9517733964463548, 3.0, 5.0], [1.9795950329900478, 3.0, 6.0], [1.9517693275746322, 3.0, 7.0], [1.95174574095154, 3.0, 8.0], [1.951748305195268, 3.0, 9.0], [1.9795886074404196, 3.0, 10.0], [1.9503890470220449, 4.0, 0.0], [1.9531512374930224, 4.0, 1.0], [1.9795974886856964, 4.0, 2.0], [1.979835524382147, 5.0, 1.0], [1.951757799436511, 5.0, 2.0], [1.9517733964463553, 5.0, 3.0], [1.9504414732647708, 6.0, 0.0], [1.9531610089559097, 6.0, 1.0], [1.9795950329900482, 6.0, 3.0], [1.979834402054918, 7.0, 1.0], [1.9517600845630658, 7.0, 2.0], [1.9517693275746322, 7.0, 3.0], [1.9798389506011282, 8.0, 0.0], [1.951771254708236, 8.0, 2.0], [1.95174574095154, 8.0, 3.0], [1.9798343778296037, 9.0, 0.0], [1.9517677955041268, 9.0, 2.0], [1.9517483051952684, 9.0, 3.0], [1.953179704207387, 10.0, 0.0], [1.9504205498209986, 10.0, 1.0], [1.9795886074404199, 10.0, 3.0], [1.953131028751234, 11.0, 0.0], [1.9504049525675535, 11.0, 1.0], [1.9795975276683213, 11.0, 2.0]]
sp2 = ['Ti', 'Ti', 'Ti', 'Ti', 'O', 'O', 'O', 'O', 'O', 'O', 'O', 'O']
import math
recs = records
mats = [m1, m2]
sps = [sp1, sp2]
entry_res = []
all_site = []
for k in range(2):
    rec = recs[k]
    cat = rec['cation']
    R0 = rec['cation_oxygen_R0_angstrom']
    B = rec['cation_oxygen_B_angstrom']
    cut = rec['declared_heteronuclear_cutoff_angstrom']
    cv = rec['cation_formal_valence']
    ov = rec['oxygen_formal_valence_magnitude']
    sp = sps[k]
    mat = mats[k]
    sums = [0.0] * len(sp)
    used = 0
    for row in mat:
        d = float(row[0])
        if d <= cut + 1e-8:
            i = int(round(float(row[1])))
            m = int(round(float(row[2])))
            sc = sp[i]
            sn = sp[m]
            if (sc == cat and sn == 'O') or (sc == 'O' and sn == cat):
                sums[i] = sums[i] + math.exp((R0 - d) / B)
                used = used + 1
    sr = []
    for i in range(len(sp)):
        fv = cv if sp[i] == cat else ov
        sr = sr + [abs(sums[i] - fv) / fv]
    entry_res = entry_res + [max(sr)]
    all_site = all_site + sr
    print('ENTRY', k, rec['record_id'], rec['formula'], 'heteronuclear_contacts_used', used, 'entry_residual', entry_res[k])
    print('SITE_SUMS', k, [round(s, 10) for s in sums])
    print('SITE_RELATIVE_DEVIATIONS', k, [round(r, 10) for r in sr])
review = []
for k in range(2):
    if entry_res[k] > 0.05:
        review = review + [recs[k]['record_id']]
print('RESULT', {'review_entry_ids': review, 'largest_site_relative_residual': round(max(all_site), 12), 'entry_residuals': entry_res})
