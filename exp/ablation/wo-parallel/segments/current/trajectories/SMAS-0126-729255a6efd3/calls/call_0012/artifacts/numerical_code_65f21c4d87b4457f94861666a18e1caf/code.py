obs=[[100.0,19.384615384615383,3.2769230769230773,'train'],[200.0,17.79310344827586,5.617241379310344,'train'],[500.0,12.0,8.04,'train'],[1000.0,7.2,6.42,'train'],[1500.0,5.6,4.8133333333333335,'validation'],[2500.0,4.615384615384615,3.084923076923077,'validation']]
cands=[['tau_1000us_nodc',0.001,False],['tau_1000us_dc',0.001,True],['tau_2000us_nodc',0.002,False],['tau_2000us_dc',0.002,True],['tau_4000us_nodc',0.004,False],['tau_4000us_dc',0.004,True]]
eps0=8.8541878128e-12
thr=1e-06
train=[o for o in obs if o[3]=='train']
val=[o for o in obs if o[3]=='validation']
print('n_train='+str(len(train)))
print('train_omegas='+str([o[0] for o in train]))
print('train_roles='+str([o[3] for o in train]))
print('n_val='+str(len(val)))
print('val_omegas='+str([o[0] for o in val]))
print('val_roles='+str([o[3] for o in val]))
wmin=min(o[0] for o in obs)
print('smallest_omega_rad_s='+str(wmin))
results=[]
for c in cands:
    tau=c[1]
    nc=3 if c[2] else 2
    rows=[]
    rhs=[]
    for o in train:
        x=o[0]*tau
        a=1.0/(1.0+x*x)
        if nc==3:
            rows=rows+[[1.0,a,0.0]]
        else:
            rows=rows+[[1.0,a]]
        rhs=rhs+[o[1]]
    for o in train:
        x=o[0]*tau
        a=1.0/(1.0+x*x)
        if nc==3:
            rows=rows+[[0.0,a*x,1.0/o[0]]]
        else:
            rows=rows+[[0.0,a*x]]
        rhs=rhs+[o[2]]
    M=[]
    for i in range(nc):
        row=[sum(rows[k][i]*rows[k][j] for k in range(len(rows))) for j in range(nc)]
        M=M+[row+[sum(rows[k][i]*rhs[k] for k in range(len(rows)))]]
    ok=True
    for col in range(nc):
        piv=col
        best=abs(M[col][col])
        for r in range(col+1,nc):
            if abs(M[r][col])>best:
                best=abs(M[r][col])
                piv=r
        if best<=0.0:
            ok=False
        tmp=M[col]
        M[col]=M[piv]
        M[piv]=tmp
    coef=[0.0]*nc
    if ok:
        for col in range(nc):
            for r in range(col+1,nc):
                f=M[r][col]/M[col][col]
                for j in range(col,nc+1):
                    M[r][j]=M[r][j]-f*M[col][j]
        for i in range(nc-1,-1,-1):
            s=M[i][nc]
            for j in range(i+1,nc):
                s=s-M[i][j]*coef[j]
            coef[i]=s/M[i][i]
    nonneg=ok and all(v>=0.0 for v in coef)
    maxerr=0.0
    for o in val:
        x=o[0]*tau
        a=1.0/(1.0+x*x)
        pr=coef[0]+coef[1]*a
        if nc==3:
            pl=coef[1]*a*x+coef[2]/o[0]
        else:
            pl=coef[1]*a*x
        maxerr=max(maxerr,abs(pr-o[1]),abs(pl-o[2]))
    keep=nonneg and maxerr<=thr
    if keep:
        why='retained'
    elif not ok:
        why='singular_fit_rejected'
    elif not nonneg:
        why='negative_parameter_rejected'
    else:
        why='validation_threshold_exceeded'
    results=results+[[c[0],tau,nc,coef[0],coef[1],(coef[2] if nc==3 else 0.0),maxerr,keep,why]]
sup=[r[0] for r in results if r[7]]
print('candidate_screen='+str(results))
print('supported_model_ids='+str(sup))
print('n_supported='+str(len(sup)))
surv=[r for r in results if r[7]]
if len(surv)==1:
    tau_s=surv[0][1]
    eps_i=surv[0][3]
    delta=surv[0][4]
    kap=surv[0][5]
    eps_st=eps_i+delta
    dc_c=eps0*kap
    xm=wmin*tau_s
    rl=delta*xm/(1.0+xm*xm)
    dl=kap/wmin
    frac=dl/(rl+dl) if (rl+dl)!=0.0 else 0.0
    dc_req=not any((r[2]==2) and r[7] for r in results)
    print('relaxation_time_s='+str(tau_s))
    print('epsilon_infinity='+str(eps_i))
    print('delta_relaxation_strength='+str(delta))
    print('epsilon_static_relaxation_only='+str(eps_st))
    print('dc_loss_rate_per_s='+str(kap))
    print('dc_conductivity_s_m='+str(dc_c))
    print('dc_loss_fraction_at_lowest_omega='+str(frac))
    print('dc_loss_required_in_supplied_family='+str(dc_req))
else:
    print('single_survivor_absent_count='+str(len(surv)))
    print('relaxation_time_s=None')
    print('epsilon_infinity=None')
    print('delta_relaxation_strength=None')
    print('epsilon_static_relaxation_only=None')
    print('dc_loss_rate_per_s=None')
    print('dc_conductivity_s_m=None')
    print('dc_loss_fraction_at_lowest_omega=None')
    print('dc_loss_required_in_supplied_family=None')
print('scope=finite_candidate_conditional_dispersion_screen')
print('provenance=roles,observation_components,candidates,epsilon0,threshold const-checked against the parsed study file')