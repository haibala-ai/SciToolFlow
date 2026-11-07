import math
n0 = 1.0
P0 = 1.0
pstd = 1.0
Kp = 1.0
RT = 2.5
dU_rxn = -10.0
a1 = 4.0*Kp*P0 + pstd
b1 = -(4.0*Kp*P0*n0 + pstd*n0)
c1 = Kp*P0*n0*n0
disc1 = b1*b1 - 4.0*a1*c1
sq1 = math.sqrt(disc1)
cands1 = [(-b1 - sq1)/(2.0*a1), (-b1 + sq1)/(2.0*a1)]
phys1 = [r for r in cands1 if r >= -1e-12 and r <= 0.5 + 1e-12 and n0 - 2.0*r >= -1e-12]
a2 = 4.0*Kp*P0
b2 = -(4.0*Kp*P0*n0 + pstd*pstd*n0)
c2 = Kp*P0*n0*n0
disc2 = b2*b2 - 4.0*a2*c2
sq2 = math.sqrt(disc2)
cands2 = [(-b2 - sq2)/(2.0*a2), (-b2 + sq2)/(2.0*a2)]
phys2 = [r for r in cands2 if r >= -1e-12 and r <= 0.5 + 1e-12 and n0 - 2.0*r >= -1e-12]
print('case1_candidate_roots', cands1)
print('case1_physical_root_count', len(phys1))
print('case2_candidate_roots', cands2)
print('case2_physical_root_count', len(phys2))
xi1 = max(0.0, min(0.5, phys1[0]))
xi2 = max(0.0, min(0.5, phys2[0]))
nM1 = n0 - 2.0*xi1
nD1 = xi1
nt1 = nM1 + nD1
nM2 = n0 - 2.0*xi2
nD2 = xi2
nt2 = nM2 + nD2
V0 = n0*RT/(P0*100.0)
P1 = P0
Vf1 = nt1*RT/(P1*100.0)
W1 = P1*100.0*(Vf1 - V0)
vr1 = Vf1/V0
Vf2 = V0
P2 = nt2*RT/(V0*100.0)
W2 = 0.0
vr2 = Vf2/V0
Q1 = xi1*dU_rxn + W1
Q2 = xi2*dU_rxn + W2
yD1 = nD1/nt1
yM1 = nM1/nt1
Kp1 = yD1*pstd/(pow(yM1, 2)*P1)
yD2 = nD2/nt2
yM2 = nM2/nt2
Kp2 = yD2*pstd/(pow(yM2, 2)*P2)
same = abs(xi1 - xi2) <= 1e-12
print('Kp_recheck_case1', Kp1)
print('Kp_recheck_case2', Kp2)
print('monomer_nonnegative_case1', nM1 >= 0.0)
print('monomer_nonnegative_case2', nM2 >= 0.0)
print('extent_leq_half_case1', xi1 <= 0.5)
print('extent_leq_half_case2', xi2 <= 0.5)
print('equilibrium_dimerization_extents_mol_by_case: [' + str(xi1) + ', ' + str(xi2) + ']')
print('final_total_gas_moles_by_case: [' + str(nt1) + ', ' + str(nt2) + ']')
print('final_pressures_bar_by_case: [' + str(P1) + ', ' + str(P2) + ']')
print('final_volume_over_initial_volume_by_case: [' + str(vr1) + ', ' + str(vr2) + ']')
print('work_by_gas_kJ_by_case: [' + str(W1) + ', ' + str(W2) + ']')
print('heat_into_gas_kJ_by_case: [' + str(Q1) + ', ' + str(Q2) + ']')
print('mechanical_boundary_leaves_equilibrium_extent_unchanged: ' + str(bool(same)))