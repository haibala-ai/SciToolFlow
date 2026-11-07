import numpy as np

obs = [{'omega_rad_s': 100, 'epsilon_real': 19.384615384615383, 'epsilon_loss_positive': 3.2769230769230773, 'role': 'train'}, {'omega_rad_s': 200, 'epsilon_real': 17.79310344827586, 'epsilon_loss_positive': 5.617241379310344, 'role': 'train'}, {'omega_rad_s': 500, 'epsilon_real': 12.0, 'epsilon_loss_positive': 8.04, 'role': 'train'}, {'omega_rad_s': 1000, 'epsilon_real': 7.2, 'epsilon_loss_positive': 6.42, 'role': 'train'}, {'omega_rad_s': 1500, 'epsilon_real': 5.6, 'epsilon_loss_positive': 4.8133333333333335, 'role': 'validation'}, {'omega_rad_s': 2500, 'epsilon_real': 4.615384615384615, 'epsilon_loss_positive': 3.084923076923077, 'role': 'validation'}]

cands = [{'id': 'tau_1000us_nodc', 'tau_s': 0.001, 'include_dc': False}, {'id': 'tau_1000us_dc', 'tau_s': 0.001, 'include_dc': True}, {'id': 'tau_2000us_nodc', 'tau_s': 0.002, 'include_dc': False}, {'id': 'tau_2000us_dc', 'tau_s': 0.002, 'include_dc': True}, {'id': 'tau_4000us_nodc', 'tau_s': 0.004, 'include_dc': False}, {'id': 'tau_4000us_dc', 'tau_s': 0.004, 'include_dc': True}]

eps0 = 8.8541878128e-12
thr = 1e-06

train = [o for o in obs if o['role'] == 'train']
val = [o for o in obs if o['role'] == 'validation']
print('n_train=' + str(len(train)) + ' n_val=' + str(len(val)))
print('epsilon0_f_m=' + str(eps0) + ' validation_threshold=' + str(thr))
supported = []
detail = {}
for c in cands:
    tau = c['tau_s']
    dc = c['include_dc']
    npar = 2
    if dc:
        npar = 3
    nrow = 2 * len(train)
    A = np.zeros((nrow, npar))
    b = np.zeros(nrow)
    for i in range(len(train)):
        w = train[i]['omega_rad_s']
        x = w * tau
        ar = 1.0 / (1.0 + x * x)
        br = x * ar
        A[2 * i, 0] = 1.0
        A[2 * i, 1] = ar
        b[2 * i] = train[i]['epsilon_real']
        A[2 * i + 1, 1] = br
        if dc:
            A[2 * i + 1, 2] = 1.0 / w
        b[2 * i + 1] = train[i]['epsilon_loss_positive']
    AtA = np.dot(A.transpose(), A)
    Atb = np.dot(A.transpose(), b)
    M = np.zeros((npar, npar + 1))
    for i in range(npar):
        for j in range(npar):
            M[i, j] = AtA[i, j]
        M[i, npar] = Atb[i]
    ok = True
    for col in range(npar):
        piv = col
        for r in range(col + 1, npar):
            if abs(M[r, col]) > abs(M[piv, col]):
                piv = r
        if abs(M[piv, col]) < 1e-300:
            ok = False
        for j in range(npar + 1):
            tmp = M[col, j]
            M[col, j] = M[piv, j]
            M[piv, j] = tmp
        pv = M[col, col]
        for j in range(col, npar + 1):
            M[col, j] = M[col, j] / pv
        for r in range(npar):
            if r != col:
                fac = M[r, col]
                for j in range(col, npar + 1):
                    M[r, j] = M[r, j] - fac * M[col, j]
    sol = []
    for i in range(npar):
        sol = sol + [M[i, npar]]
    neg = False
    for s in sol:
        if s < 0.0:
            neg = True
    maxerr = 0.0
    for v in val:
        w = v['omega_rad_s']
        x = w * tau
        ar = 1.0 / (1.0 + x * x)
        br = x * ar
        pr = sol[0] + sol[1] * ar
        pl = sol[1] * br
        if dc:
            pl = pl + sol[2] / w
        e1 = abs(pr - v['epsilon_real'])
        e2 = abs(pl - v['epsilon_loss_positive'])
        if e1 > maxerr:
            maxerr = e1
        if e2 > maxerr:
            maxerr = e2
    print('candidate=' + c['id'] + ' tau_s=' + str(tau) + ' dc=' + str(dc) + ' fitted=' + str(sol) + ' max_validation_component_error=' + str(maxerr) + ' negative_parameter=' + str(neg))
    if (not neg) and ok and maxerr <= thr:
        supported = supported + [c['id']]
        detail[c['id']] = {'tau': tau, 'dc': dc, 'sol': sol, 'maxerr': maxerr}
print('supported_model_ids=' + str(supported))
print('n_supported=' + str(len(supported)))
if len(supported) > 0:
    anynodc = False
    for s in supported:
        if not detail[s]['dc']:
            anynodc = True
    print('dc_loss_required_in_supplied_family=' + str(not anynodc))
if len(supported) == 1:
    sid = supported[0]
    d = detail[sid]
    tau = d['tau']
    sol = d['sol']
    eps_inf = sol[0]
    delta = sol[1]
    kappa = 0.0
    if d['dc']:
        kappa = sol[2]
    sigma = eps0 * kappa
    ws = []
    for o in obs:
        ws = ws + [o['omega_rad_s']]
    wmin = min(ws)
    x = wmin * tau
    relax_loss = delta * x / (1.0 + x * x)
    dc_loss = kappa / wmin
    total = relax_loss + dc_loss
    dcf = 0.0
    if total != 0.0:
        dcf = dc_loss / total
    print('survivor_id=' + sid)
    print('relaxation_time_s=' + str(tau))
    print('epsilon_infinity=' + str(eps_inf))
    print('delta=' + str(delta))
    print('epsilon_static_relaxation_only=' + str(eps_inf + delta))
    print('dc_loss_rate_per_s=' + str(kappa))
    print('dc_conductivity_s_m=' + str(sigma))
    print('lowest_omega_rad_s=' + str(wmin))
    print('relaxation_loss_at_lowest_omega=' + str(relax_loss))
    print('dc_loss_at_lowest_omega=' + str(dc_loss))
    print('dc_loss_fraction_at_lowest_omega=' + str(dcf))
    print('scope=finite_candidate_conditional_dispersion_screen')
else:
    print('no unique survivor: survivor parameters not reported')
