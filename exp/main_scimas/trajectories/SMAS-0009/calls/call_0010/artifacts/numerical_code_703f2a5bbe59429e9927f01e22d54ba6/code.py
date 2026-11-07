spiro_a = 1
spiro_b = 0
spiro_c = 0
bridgehead_a = 0
bridgehead_b = 2
bridgehead_c = 0
spiro_counts = [spiro_a, spiro_b, spiro_c]
bridgehead_counts = [bridgehead_a, bridgehead_b, bridgehead_c]
ids = ['a', 'b', 'c']
max_spiro = max(spiro_counts)
selected = [ids[i] for i in range(3) if abs(spiro_counts[i] - max_spiro) <= 1e-9]
print('spiro_present_a', spiro_counts[0] > 0)
print('spiro_present_b', spiro_counts[1] > 0)
print('spiro_present_c', spiro_counts[2] > 0)
print('bridgehead_present_a', bridgehead_counts[0] > 0)
print('bridgehead_present_b', bridgehead_counts[1] > 0)
print('bridgehead_present_c', bridgehead_counts[2] > 0)
print('max_spiro', max_spiro)
print('selected', selected)
print('spiro_counts', spiro_counts)
print('bridgehead_counts', bridgehead_counts)