study = {'kind': 'controlled_debye_plus_dc_study', 'observations': [{'omega_rad_s': 100, 'epsilon_real': 19.384615384615383, 'epsilon_loss_positive': 3.2769230769230773, 'role': 'train'}, {'omega_rad_s': 200, 'epsilon_real': 17.79310344827586, 'epsilon_loss_positive': 5.617241379310344, 'role': 'train'}, {'omega_rad_s': 500, 'epsilon_real': 12.0, 'epsilon_loss_positive': 8.04, 'role': 'train'}, {'omega_rad_s': 1000, 'epsilon_real': 7.2, 'epsilon_loss_positive': 6.42, 'role': 'train'}, {'omega_rad_s': 1500, 'epsilon_real': 5.6, 'epsilon_loss_positive': 4.8133333333333335, 'role': 'validation'}, {'omega_rad_s': 2500, 'epsilon_real': 4.615384615384615, 'epsilon_loss_positive': 3.084923076923077, 'role': 'validation'}], 'candidate_models': [{'id': 'tau_1000us_nodc', 'tau_s': 0.001, 'include_dc': False}, {'id': 'tau_1000us_dc', 'tau_s': 0.001, 'include_dc': True}, {'id': 'tau_2000us_nodc', 'tau_s': 0.002, 'include_dc': False}, {'id': 'tau_2000us_dc', 'tau_s': 0.002, 'include_dc': True}, {'id': 'tau_4000us_nodc', 'tau_s': 0.004, 'include_dc': False}, {'id': 'tau_4000us_dc', 'tau_s': 0.004, 'include_dc': True}], 'epsilon0_f_m': 8.8541878128e-12, 'validation_max_absolute_component_error': 1e-06, 'physical_parameter_lower_bounds': {'epsilon_infinity': 0, 'relaxation_strength': 0, 'dc_loss_rate_per_s': 0}, 'boundary_policy': 'Nonnegative parameters are admissible; no clipping or refitting on validation rows.'}
obs = study['observations']
train = [o for o in obs if o['role'] == 'train']
valid = [o for o in obs if o['role'] == 'validation']
cands = study['candidate_models']
eps0 = float(study['epsilon0_f_m'])
thr = float(study['validation_max_absolute_component_error'])
fits = {}
for cand in cands:
    tau = float(cand['tau_s'])
    inc = bool(cand['include_dc'])
    npar = 3 if inc else 2
    A = []
    b = []
    for o in train:
        w = float(o['omega_rad_s'])
        x = w * tau
        d = 1.0 + x * x
        if inc:
            A = A + [[1.0, 1.0 / d, 0.0], [0.0, x / d, 1.0 / w]]
        else:
            A = A + [[1.0, 1.0 / d], [0.0, x / d]]
        b = b + [float(o['epsilon_real']), float(o['epsilon_loss_positive'])]
    M = [[sum([row[i] * row[j] for row in A]) for j in range(npar)] for i in range(npar)]
    rhs = [sum([A[k][i] * b[k] for k in range(len(b))]) for i in range(npar)]
    aug = [[M[i][j] for j in range(npar)] + [rhs[i]] for i in range(npar)]
    for col in range(npar):
        piv = col
        for r in range(col + 1, npar):
            if abs(aug[r][col]) > abs(aug[piv][col]):
                piv = r
        tmp = [aug[col][c] for c in range(npar + 1)]
        aug[col] = [aug[piv][c] for c in range(npar + 1)]
        aug[piv] = tmp
        pv = aug[col][col]
        for r in range(col + 1, npar):
            fac = aug[r][col] / pv
            for c in range(col, npar + 1):
                aug[r][c] = aug[r][c] - fac * aug[col][c]
    sol = [0.0] * npar
    for i in range(npar - 1, -1, -1):
        s = aug[i][npar]
        for j in range(i + 1, npar):
            s = s - aug[i][j] * sol[j]
        sol[i] = s / aug[i][i]
    eps_inf = sol[0]
    delta = sol[1]
    kappa = sol[2] if inc else 0.0
    okpar = (eps_inf >= 0.0) and (delta >= 0.0) and (kappa >= 0.0)
    merr = 0.0
    for o in valid:
        w = float(o['omega_rad_s'])
        x = w * tau
        d = 1.0 + x * x
        pr = eps_inf + delta / d
        pl = delta * x / d + (kappa / w if inc else 0.0)
        merr = max(merr, abs(pr - float(o['epsilon_real'])), abs(pl - float(o['epsilon_loss_positive'])))
    supported = okpar and (merr <= thr)
    fits[cand['id']] = {'tau_s': tau, 'include_dc': inc, 'epsilon_infinity': eps_inf, 'Delta': delta, 'kappa': kappa, 'max_validation_abs_error': merr, 'nonnegative': okpar, 'supported': supported}
    print('candidate', cand['id'], 'tau', tau, 'include_dc', inc, 'epsilon_infinity', eps_inf, 'Delta', delta, 'kappa', kappa, 'max_validation_abs_error', merr, 'nonnegative', okpar, 'supported', supported)
supported_ids = [c['id'] for c in cands if fits[c['id']]['supported']]
print('supported_model_ids', supported_ids)
print('validation_threshold', thr)
print('candidate_fits', fits)
n_dc = len([m for m in supported_ids if fits[m]['include_dc']])
n_nodc = len([m for m in supported_ids if not fits[m]['include_dc']])
print('n_supported_dc', n_dc, 'n_supported_nodc', n_nodc)
print('dc_loss_required_in_supplied_family', (n_dc > 0) and (n_nodc == 0))
if len(supported_ids) == 1:
    sid = supported_ids[0]
    sf = fits[sid]
    tau_out = sf['tau_s']
    eps_inf_out = sf['epsilon_infinity']
    eps_static_out = sf['epsilon_infinity'] + sf['Delta']
    kappa_out = sf['kappa']
    dc_cond_out = eps0 * kappa_out
    w_low = min([float(o['omega_rad_s']) for o in obs])
    x = w_low * tau_out
    d = 1.0 + x * x
    relax_loss = sf['Delta'] * x / d
    dc_loss = kappa_out / w_low
    total_loss = relax_loss + dc_loss
    frac = dc_loss / total_loss if total_loss != 0.0 else 0.0
    print('surviving_model_id', sid)
    print('relaxation_time_s', tau_out)
    print('epsilon_infinity', eps_inf_out)
    print('relaxation_strength_Delta', sf['Delta'])
    print('epsilon_static_relaxation_only', eps_static_out)
    print('dc_loss_rate_per_s', kappa_out)
    print('epsilon0_f_m', eps0)
    print('dc_conductivity_s_m', dc_cond_out)
    print('lowest_omega_rad_s', w_low)
    print('dc_loss_at_lowest_omega', dc_loss)
    print('relax_loss_at_lowest_omega', relax_loss)
    print('total_loss_at_lowest_omega', total_loss)
    print('dc_loss_fraction_at_lowest_omega', frac)
else:
    print('single_survivor_status', 'not_one', 'supported_model_ids', supported_ids)
print('scope', 'finite_candidate_conditional_dispersion_screen')
print('dc_is_not_extra_static_permittivity', True)
print('unique_microscopic_mechanism_established', False)
print('continuous_tau_uncertainty_established', False)