obs = [(100.0, 19.384615384615383, 3.2769230769230773, "train"), (200.0, 17.79310344827586, 5.617241379310344, "train"), (500.0, 12.0, 8.04, "train"), (1000.0, 7.2, 6.42, "train"), (1500.0, 5.6, 4.8133333333333335, "validation"), (2500.0, 4.615384615384615, 3.084923076923077, "validation")]
cands = [("tau_1000us_nodc", 0.001, False), ("tau_1000us_dc", 0.001, True), ("tau_2000us_nodc", 0.002, False), ("tau_2000us_dc", 0.002, True), ("tau_4000us_nodc", 0.004, False), ("tau_4000us_dc", 0.004, True)]
eps0 = 8.8541878128e-12
thr = 1e-06
train = [o for o in obs if o[3] == "train"]
val = [o for o in obs if o[3] == "validation"]
m = 2*len(train)
report = []
for c in cands:
    cid = c[0]
    tau = c[1]
    dcf = int(c[2])
    n = 2 + dcf
    X = [[1.0, 1.0/(1.0+(o[0]*tau)**2)] + [0.0]*dcf for o in train] + [[0.0, o[0]*tau/(1.0+(o[0]*tau)**2)] + [1.0/o[0]]*dcf for o in train]
    b = [o[1] for o in train] + [o[2] for o in train]
    N = [[sum([X[i][j]*X[i][k] for i in range(m)]) for k in range(n)] for j in range(n)]
    r = [sum([X[i][j]*b[i] for i in range(m)]) for j in range(n)]
    for col in range(n):
        for rr in range(col+1, n):
            f = N[rr][col]/N[col][col]
            for cc in range(col, n):
                N[rr][cc] = N[rr][cc] - f*N[col][cc]
            r[rr] = r[rr] - f*r[col]
    sol = [0.0]*n
    for i in range(n-1, -1, -1):
        s = r[i]
        for j in range(i+1, n):
            s = s - N[i][j]*sol[j]
        sol[i] = s/N[i][i]
    e_inf = sol[0]
    delta = sol[1]
    kappa = (sol + [0.0])[2]
    errs = []
    for o in val:
        xv = o[0]*tau
        errs = errs + [abs(e_inf + delta/(1.0+xv*xv) - o[1]), abs(delta*xv/(1.0+xv*xv) + kappa/o[0] - o[2])]
    mae = max(errs)
    adm = min(sol) >= 0.0
    report = report + [{"id": cid, "tau_s": tau, "include_dc": c[2], "eps_infinity": e_inf, "delta": delta, "kappa": kappa, "admissible": adm, "max_abs_validation_error": mae, "supported": (adm and mae <= thr), "epsilon_static_relaxation_only": e_inf + delta, "dc_conductivity_s_m": eps0*kappa}]
print(report)
supp = [d for d in report if d["supported"]]
print("N_SUPPORTED", len(supp))
print("SUPPORTED_IDS", [d["id"] for d in supp])
surv = supp + [{"id": "NONE", "tau_s": 0.0, "eps_infinity": 0.0, "delta": 0.0, "kappa": 0.0, "include_dc": False, "epsilon_static_relaxation_only": 0.0, "dc_conductivity_s_m": 0.0}]
s0 = surv[0]
ndc = sum([1 for d in supp if d["include_dc"]])
nnd = len(supp) - ndc
dc_required = (len(supp) > 0) and (ndc > 0) and (nnd == 0)
w_low = min([o[0] for o in obs])
xk = w_low*s0["tau_s"]
dl = s0["delta"]*xk/(1.0 + xk*xk)
dcl = s0["kappa"]/w_low
frac = dcl/(dl + dcl + 1e-300)
print("SURVIVOR_ID", s0["id"])
print("TAU_S", s0["tau_s"])
print("EPS_INF", s0["eps_infinity"])
print("EPS_STATIC_RELAX_ONLY", s0["epsilon_static_relaxation_only"])
print("KAPPA_LOSS_RATE", s0["kappa"])
print("SIGMA_DC_S_M", s0["dc_conductivity_s_m"])
print("LOWEST_OMEGA", w_low)
print("DC_LOSS_AT_LOWEST", dcl)
print("RELAX_LOSS_AT_LOWEST", dl)
print("DC_FRACTION_AT_LOWEST", frac)
print("DC_REQUIRED_IN_FAMILY", dc_required)
print("SCOPE", "finite_candidate_conditional_dispersion_screen")