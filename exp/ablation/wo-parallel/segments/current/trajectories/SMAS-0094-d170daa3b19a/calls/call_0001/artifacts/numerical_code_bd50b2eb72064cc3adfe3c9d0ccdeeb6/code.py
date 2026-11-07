truth = [[0,1,2,3],[1,2,3,4],[-1,0,1,2]]
pred = [[[0.1,1.1,2.1,3.1],[1.2,2.2,3.2,4.2],[1.0,2.0,3.0,4.0]],[[0.5,1.5,2.5,3.5],[1.5,2.5,3.5,4.5],[-0.5,0.5,1.5,2.5]],[[1.0,2.0,3.0,4.0],[1.0,2.0,3.0,4.0],[-0.6,0.4,1.4,2.4]]]
nominal = [0.9,0.05,0.05]
bounds = [[0.2,0.9],[0.05,0.7],[0.05,0.6]]
cohort_mse = [[sum((pred[m][c][s]-truth[c][s])**2 for s in range(4))/4.0 for c in range(3)] for m in range(3)]
vertices = [[bounds[i][bi] if t==i else bounds[j][bj] if t==j else 1.0 - bounds[i][bi] - bounds[j][bj] for t in range(3)] for i in range(3) for j in range(i+1,3) for bi in range(2) for bj in range(2)]
vertices = [w for w in vertices if all(w[t] >= bounds[t][0]-1e-12 and w[t] <= bounds[t][1]+1e-12 for t in range(3))]
risk_matrix = [[sum(cohort_mse[m][t]*w[t] for t in range(3)) for w in vertices] for m in range(3)]
worst_risks = [max(risk_matrix[m]) for m in range(3)]
worst_weights = [[w for z,w in zip(risk_matrix[m], vertices) if abs(z - worst_risks[m]) < 1e-12][0] for m in range(3)]
nominal_risks = [sum(cohort_mse[m][t]*nominal[t] for t in range(3)) for m in range(3)]
witness_risks = [sum(cohort_mse[m][t]*worst_weights[m][t] for t in range(3)) for m in range(3)]
robust_selected = [['a','b','c'][m] for m in range(3) if abs(worst_risks[m] - min(worst_risks)) <= 1e-9]
nominal_selected = [['a','b','c'][m] for m in range(3) if abs(nominal_risks[m] - min(nominal_risks)) <= 1e-9]
print('cohort_mse', cohort_mse)
print('worst_risks', worst_risks)
print('nominal_risks', nominal_risks)
print('witness_risks', witness_risks)
print('robust_selected', robust_selected)
print('nominal_selected', nominal_selected)