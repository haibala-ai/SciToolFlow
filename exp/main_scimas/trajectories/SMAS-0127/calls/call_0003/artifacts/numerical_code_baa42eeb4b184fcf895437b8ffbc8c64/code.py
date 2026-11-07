n_Fe = 3
n_O = 4
oxygen_valence = -2
allowed = [2, 3]
labels = ['Fe(II)', 'Fe(III)']
areas = [0.5, 0.5]
factors = [2.0, 1.0]

target_charge = -oxygen_valence * n_O
lo = min(allowed)
hi = max(allowed)
n_hi = (target_charge - lo * n_Fe) / (hi - lo)
n_lo = n_Fe - n_hi
neutral_counts = [n_lo, n_hi]
print('line_labels', labels)
print('observed_normalized_areas', areas)
print('per_ion_response_factors', factors)
print('charge_target_from_neutrality', target_charge)
print('neutral_counts_from_stoichiometry', neutral_counts)

signal = [areas[0] / factors[0], areas[1] / factors[1]]
print('response_corrected_signal', signal)
total_signal = signal[0] + signal[1]
frac = [signal[0] / total_signal, signal[1] / total_signal]
print('response_corrected_fractions', frac)
implied = [n_Fe * frac[0], n_Fe * frac[1]]
print('implied_Fe_II_Fe_III_counts', implied)

consistent = abs(implied[0] - neutral_counts[0]) < 1e-9 and abs(implied[1] - neutral_counts[1]) < 1e-9
print('response_corrected_spectral_areas_consistent', consistent)

raw_equal = abs(areas[0] - areas[1]) < 1e-12
ratio = implied[0] / implied[1]
print('raw_areas_equal', raw_equal)
print('implied_Fe_II_over_Fe_III_count_ratio', ratio)
print('equal_raw_line_areas_imply_equal_Fe_II_and_Fe_III_counts', raw_equal and abs(ratio - 1.0) < 1e-12)
print('reason', 'equal raw areas map to equal ion counts only when the per-ion response factors are equal')
