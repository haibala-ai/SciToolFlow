ae = [0.18049038507585172, 0.8864589767164677, 1.1330506382076813]
re = [-6.3536079833838e-17, 0.844662803400772, 0.976505079810907]
rev = [[0.7525766947068779, 0.4770926753058897, 0.4538842338675576], [-0.6585046078685183, 0.5452487717781598, 0.5187248387057806], [6.84320866013802e-17, -0.6892650840162132, 0.7245092435270394]]
import math
ae = ae
re = re
rev = rev
min_aff = ae[0]
zero = []
for i in range(len(re)):
    if abs(re[i]) <= 1e-9:
        zero = zero + [i]
nullity = len(zero)
trans = None
shear = None
if nullity == 1:
    j = zero[0]
    v0 = rev[0][j]
    v1 = rev[1][j]
    v2 = rev[2][j]
    if abs(v0) > 1e-12:
        trans = v1/v0
        shear = (v2/math.sqrt(2.0))/v0
proves = (min_aff > 1e-9 and nullity == 0)
s_trans = 'null'
if trans is not None:
    s_trans = str(trans)
s_shear = 'null'
if shear is not None:
    s_shear = str(shear)
s_proves = 'true'
if not proves:
    s_proves = 'false'
q = '"'
print('{' + q + 'minimum_affine_kelvin_stiffness_ev_angstrom2' + q + ': ' + str(min_aff) + ', ' + q + 'relaxed_uniform_strain_nullity' + q + ': ' + str(nullity) + ', ' + q + 'guest_transverse_over_axial_strain' + q + ': ' + s_trans + ', ' + q + 'guest_tensor_shear_over_axial_strain' + q + ': ' + s_shear + ', ' + q + 'positive_affine_response_proves_uniform_strain_rigidity' + q + ': ' + s_proves + ', ' + q + 'scope' + q + ': ' + q + 'periodic_2d_unstressed_bar_internal_relaxation' + q + '}')