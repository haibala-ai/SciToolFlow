times = [0, 0.4, 1.1, 2, 3]
sensors = [[0, 0.16, 1.21, 4, 9], [0, 0.5, 0.9, 1.3, 1.8], [1, 1.1, 1.4, 1.5, 1.7]]
query_times = [0.2, 0.75, 1.55, 2.5]
ids = ['a', 'b', 'c']
n = len(times)
m = len(sensors)
grads = [[0.0] * n for s0 in range(m)]
for s in range(m):
    y = sensors[s]
    g = grads[s]
    g[0] = (y[1] - y[0]) / (times[1] - times[0])
    g[n-1] = (y[n-1] - y[n-2]) / (times[n-1] - times[n-2])
    for i in range(1, n-1):
        dx1 = times[i] - times[i-1]
        dx2 = times[i+1] - times[i]
        dy1 = y[i] - y[i-1]
        dy2 = y[i+1] - y[i]
        g[i] = (dy1 / dx1 * dx2 + dy2 / dx2 * dx1) / (dx1 + dx2)
recs = [0.0] * m
for s in range(m):
    g = grads[s]
    total = 0.0
    for i in range(n-1):
        total = total + (times[i+1] - times[i]) * (g[i] + g[i+1]) / 2.0
    recs[s] = total
closures = [0.0] * m
for s in range(m):
    closures[s] = recs[s] - (sensors[s][n-1] - sensors[s][0])
midpoints = [[0.0] * len(query_times) for s0 in range(m)]
for s in range(m):
    y = sensors[s]
    g = grads[s]
    for j in range(len(query_times)):
        q = query_times[j]
        i = 0
        for k in range(n-1):
            if times[k] <= q and q <= times[k+1]:
                i = k
        x0 = times[i]
        x1 = times[i+1]
        h = x1 - x0
        t = (q - x0) / h
        h00 = 2.0 * t * t * t - 3.0 * t * t + 1.0
        h10 = t * t * t - 2.0 * t * t + t
        h01 = -2.0 * t * t * t + 3.0 * t * t
        h11 = t * t * t - t * t
        midpoints[s][j] = h00 * y[i] + h10 * h * g[i] + h01 * y[i+1] + h11 * h * g[i+1]
abs_closures = [abs(closures[s]) for s in range(m)]
min_abs = min(abs_closures)
selected = [ids[s] for s in range(m) if abs(abs_closures[s] - min_abs) <= 1e-9]
sel_str = ''
for k in range(len(selected)):
    if k > 0:
        sel_str = sel_str + ','
    sel_str = sel_str + '\x22' + selected[k] + '\x22'
out = '{\x22gradient_a\x22:' + str(grads[0]) + ',\x22recovered_change_a\x22:' + str(recs[0]) + ',\x22closure_error_a\x22:' + str(closures[0]) + ',\x22midpoint_a\x22:' + str(midpoints[0]) + ',\x22gradient_b\x22:' + str(grads[1]) + ',\x22recovered_change_b\x22:' + str(recs[1]) + ',\x22closure_error_b\x22:' + str(closures[1]) + ',\x22midpoint_b\x22:' + str(midpoints[1]) + ',\x22gradient_c\x22:' + str(grads[2]) + ',\x22recovered_change_c\x22:' + str(recs[2]) + ',\x22closure_error_c\x22:' + str(closures[2]) + ',\x22midpoint_c\x22:' + str(midpoints[2]) + ',\x22selected\x22:[' + sel_str + ']}'
print(out)