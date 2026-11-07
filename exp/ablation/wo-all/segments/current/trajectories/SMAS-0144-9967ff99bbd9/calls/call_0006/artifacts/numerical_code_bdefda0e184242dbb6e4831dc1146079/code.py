import math
bulk_volume = 15.8795999213
bulk_atoms = 2
vpa = bulk_volume / bulk_atoms
init_volume = 911.59467216
init_atoms = 112
fin_volume = 893.60140884
fin_atoms = 112
a_i = 6.00931742
b_i = 6.00931788
gamma_i = 59.99999152
area_i = a_i * b_i * math.sin(gamma_i * math.pi / 180.0)
a_f = 5.99187600
b_f = 5.99187665
gamma_f = 59.99999252
area_f = a_f * b_f * math.sin(gamma_f * math.pi / 180.0)
excess_i = init_volume - init_atoms * vpa
excess_f = fin_volume - fin_atoms * vpa
length_i = excess_i / (2.0 * area_i)
length_f = excess_f / (2.0 * area_f)
diff = length_f - length_i
ratio = area_f / area_i
print('bulk_volume_per_atom', vpa)
print('area_init', area_i)
print('area_fin', area_f)
print('excess_length_init', length_i)
print('excess_length_fin', length_f)
print('final_minus_initial_excess_length_angstrom', diff)
print('final_to_initial_interface_area_ratio', ratio)