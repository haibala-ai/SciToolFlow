"""Individually specified solid-state and computational materials investigations."""
from .common import *
from material import cif,poscar


def lattice_file(c,label,cell,sites):return c.asset(label+'.cif',cif(cell,sites))
def rock(a=4.2,first='Na',second='Cl'):return (a,a,a,90,90,90),[(first,0,0,0),(second,.5,.5,.5)]
def density(c,n,file):return c.add(n,'CalculateDensity',{'file_name':file})
def composition(c,n,file):return c.add(n,'GetElementComposition',{'file_name':file})


def phase_unmixing():
    c=Case(63,'Material','advanced','Mass and volume fractions are distinct mixture inverses',
      'Three fixed crystalline phase controls a=NaCl,b=KCl,c=NaF have supplied geometries. Report density_a etc. (g/cm^3), mass_fractions_a etc. as [Na,K,F,Cl] for the stated chemical formula, and formula_mass_a etc. (u). Observed mixture Na,K,F mass fractions are supplied. Solve their 3x3 elemental mass balance for phase mass fractions mass_weights [a,b,c], then independently forward-predict all four elemental fractions as elemental_check. Under the explicit additive-phase-volume model report volume_weights = (mass_weight/density)/sum(mass_weight/density) and mixture_density =1/sum(mass_weight/density). Do not treat mass weights as volume weights or infer a reacted single phase.',
      {},'phase_mass_volume_inverse','Phase composition coefficients and densities are shared by inverse and independent forward/volume branches.',
      ['Independent phase geometry/density and stoichiometry','After inversion, elemental balance and additive-volume calculations'],
      'Reconcile elemental observations, mass conservation and physical volume convention.')
    from pymatgen.core import Composition
    formula=['NaCl','KCl','NaF'];target=[.2,.3,.5];elements=['Na','K','F','Cl'];c.inputs={'formula':formula,'observed_Na_K_F':[sum(target[i]*float(Composition(f).get_wt_fraction(e)) for i,f in enumerate(formula)) for e in elements[:3]]}
    fr={};ds=[]
    for i,k in enumerate('abc'):
        cell,sites=rock([5.64,6.29,4.62][i],*[(('Na','Cl'),('K','Cl'),('Na','F'))[i]][0]);file=lattice_file(c,k,cell,sites);d=density(c,'density_'+k,file);f=c.add('fraction_'+k,'CompositionFractions',{'formula':I(f'/formula/{i}')});ds.append(N(d,'/density_g_per_cm3'))
        vals=[]
        for e in elements:
            v=N(f,'/mass_fractions/'+e) if e in Composition(formula[i]) else V(0.);fr[k,e]=v;vals.append(v)
        c.out('density_'+k,ds[-1]);c.out('mass_fractions_'+k,vector(*vals),'array');c.out('formula_mass_'+k,N(f,'/formula_mass_u'))
    A=matrix([[fr[k,e] for k in 'abc'] for e in elements[:3]]);solve=c.add('inverse','SolveLinearSystem',{'matrix_a':A,'vector_b':I('/observed_Na_K_F')});forward=c.add('forward','MatrixMultiply',{'left':matrix([[fr[k,e] for k in 'abc'] for e in elements]),'right':N(solve,'/solution')})
    specific=[E('divide',N(solve,f'/solution/{i}'),ds[i]) for i in range(3)];total=E('sum',vector(*specific));c.out('mass_weights',N(solve,'/solution'),'array');c.out('elemental_check',N(forward,'/product'),'array');c.out('volume_weights',vector(*[E('divide',v,total) for v in specific]),'array');c.out('mixture_density',E('divide',V(1),total))
    return c.emit()


def density_model():
    c=Case(64,'Material','intermediate','Held-out density calibration distinguishes reciprocal volume physics',
      'Five cells have the same CsCl atom inventory but different cubic lengths. Report volume and density arrays in file order. Train on indices[0,2,4] and evaluate indices[1,3]. Fit unpenalized linear regressions with intercept for (a) density versus volume and (b) density versus reciprocal volume. Report pred_volume,pred_reciprocal,rmse_volume,rmse_reciprocal and selected as all minimum-heldout-RMSE IDs volume,reciprocal. The reciprocal coefficient is a numerical rho*angstrom^3 scale, not directly an atomic mass in grams. Cell geometry is synthetic; no equation of state or free energy is inferred.',
      {},'reciprocal_volume_model_discrimination','The same measured geometry/density pairs feed two scientific coordinate hypotheses.',
      ['Five independent source-density measurements','Direct-volume and reciprocal-volume fitting/prediction chains'],
      'Compare held-out predictions under two coordinate models without fitting the held-out rows.')
    ds=[];vs=[]
    for i,a in enumerate([3.8,4.,4.2,4.4,4.6]):
        f=lattice_file(c,str(i),*rock(a,'Cs','Cl'));n=density(c,'density_'+str(i),f);ds.append(N(n,'/density_g_per_cm3'));vs.append(N(n,'/volume_angstrom_cubed'))
    c.out('volume',vector(*vs),'array');c.out('density',vector(*ds),'array');errors=[]
    for tag,reciprocal in [('volume',False),('reciprocal',True)]:
        xs=[E('divide',V(1),v) if reciprocal else v for v in vs];train=matrix([[xs[i]] for i in [0,2,4]]);test=matrix([[xs[i]] for i in [1,3]])
        f=c.add('fit_'+tag,'FitLinearRegression',{'training_features':train,'targets':vector(*[ds[i] for i in [0,2,4]])});p=c.add('prediction_'+tag,'PredictLinearModel',{'model':N(f,'/model'),'features':test});m=c.add('metric_'+tag,'RegressionMetrics',{'truth':vector(ds[1],ds[3]),'predicted':N(p,'/predictions')});c.out('pred_'+tag,N(p,'/predictions'),'array');c.out('rmse_'+tag,N(m,'/rmse'));errors.append(N(m,'/rmse'))
    c.selection('selected',['volume','reciprocal'],errors);return c.emit()


def cutoff_envelope():
    c=Case(65,'Material','intermediate','Coordination conclusion across a finite radial resolution envelope',
      'Compare equal-volume-per-atom bcc and fcc Fe controls. At radii[2.2,2.5,2.8,3.1] A report directed periodic contacts per supplied-cell atom as coordination_a and coordination_b. Include nonzero self images, exclude only zero-image self pairs. Report gradient_a,b using numpy.gradient edge_order1 on this radius grid and integral_a,b as trapezoidal integrals of the coordination curves. Report difference = coordination_b minus coordination_a. These are cumulative contact-resolution diagnostics, not chemical bonds or a normalized radial distribution function.',
      {'radii':[2.2,2.5,2.8,3.1]},'coordination_resolution_functional','Each fixed geometry is shared across a radial observation curve, whose samples feed two independent summaries.',
      ['Independent radius/structure neighbor computations','Gradient and integrated-contact summaries after each complete curve'],
      'Do not let a conclusion at one arbitrary cutoff stand in for the full requested resolution audit.')
    a=2.86;b=a*2**(1/3);files=[lattice_file(c,'bcc',(a,a,a,90,90,90),[('Fe',0,0,0),('Fe',.5,.5,.5)]),lattice_file(c,'fcc',(b,b,b,90,90,90),[('Fe',0,0,0),('Fe',0,.5,.5),('Fe',.5,0,.5),('Fe',.5,.5,0)])];curves=[]
    for k,file in zip('ab',files):
        values=[]
        for i,r in enumerate(c.inputs['radii']):
            n=c.add('neighbor_'+k+str(i),'PeriodicNeighborList',{'structure_file':file,'cutoff_angstrom':V(r)});values.append(E('divide',N(n,'/edge_count'),N(n,'/site_count')))
        curve=vector(*values);curves.append(values);g=c.add('gradient_'+k,'FiniteDifferenceGradient',{'x':I('/radii'),'y':curve});t=c.add('integral_'+k,'NumericalTrapezoidIntegration',{'x':I('/radii'),'y':curve});c.out('coordination_'+k,curve,'array');c.out('gradient_'+k,N(g,'/gradient'),'array');c.out('integral_'+k,N(t,'/integral'))
    c.out('difference',vector(*[E('subtract',b,a) for a,b in zip(*curves)]),'array');return c.emit()


def diffraction_nuisance():
    c=Case(66,'Material','advanced','Candidate diffraction patterns under an unknown common angle offset',
      'Three synthetic cubic salt controls a,b,c are candidate instrument standards. For each use ideal nonanomalous powder diffraction at wavelength1.5406 A, 2theta5..100deg. Extract its first THREE smallest-angle nonzero-intensity lines as theoretical_a etc. The supplied observed three angles correspond by this stated first-line order. Fit one additive zero-angle offset per candidate as the mean(observed-theoretical). Report offset_a etc., corrected_a etc.=theoretical+offset, and rmse_a etc. against observations. Select all minimum-RMSE candidates. The nuisance is an additive 2theta offset, not a wavelength or lattice rescaling; do not rank by uncorrected residual alone.',
      {'observed':[22.7,32.1,39.4]},'diffraction_with_nuisance_calibration','One fixed observed scan and candidate-specific theoretical line identities.',
      ['Independent candidate diffraction calculations','Per-candidate offset estimation and corrected prediction validation'],
      'Separate phase evidence from a common instrumental angle nuisance before comparing fits.')
    errors=[]
    for k,a,pair in [('a',4.1,('Cs','Cl')),('b',4.5,('Cs','Cl')),('c',5.1,('K','Cl'))]:
        f=lattice_file(c,k,*rock(a,*pair));p=c.add('powder_'+k,'PowderDiffractionPattern',{'structure_file':f,'wavelength_angstrom':V(1.5406),'two_theta_min_deg':V(5.),'two_theta_max_deg':V(100.)})
        theoretical=vector(*[N(p,f'/peaks/{i}/two_theta_deg') for i in range(3)]);difference=vector(*[E('subtract',I(f'/observed/{i}'),N(p,f'/peaks/{i}/two_theta_deg')) for i in range(3)])
        offset=E('divide',E('sum',difference),V(3));corrected=vector(*[E('add',N(p,f'/peaks/{i}/two_theta_deg'),offset) for i in range(3)]);m=c.add('metric_'+k,'RegressionMetrics',{'truth':I('/observed'),'predicted':corrected})
        c.out('theoretical_'+k,theoretical,'array');c.out('offset_'+k,offset);c.out('corrected_'+k,corrected,'array');c.out('rmse_'+k,N(m,'/rmse'));errors.append(N(m,'/rmse'))
    c.selection('selected',list('abc'),errors);return c.emit()


def periodic_replicates():
    c=Case(67,'Material','advanced','Periodic replicate displacement covariance with directional uncertainty',
      'Four independently generated endpoint-replicate files share one reference cell and fixed [Na,Cl] site identities. Extract exact minimum-image Na Cartesian displacements in A, preserving replicate order. Report displacements, three component means means_xyz and central95% bootstrap mean intervals intervals_xyz using1000 resamples and seed31 separately per component. Center all four displacements by their sample component means; report the unbiased3x3 covariance covariance (denominator3), ascending eigenvalues spectrum and the ratio largest/smallest eigenvalue anisotropy. A static synthetic endpoint ensemble is not a diffusion trajectory or a diffusion coefficient.',
      {},'periodic_replicate_uncertainty','One immutable reference, fixed atom correspondence, and one displacement sample matrix.',
      ['Four independent periodic matching calls','Component uncertainty estimates versus joint centered covariance/spectral analysis'],
      'Reconcile periodic image choices with uncertainty units and a joint anisotropy summary.')
    ref=c.asset('reference.vasp',poscar([[6,0,0],[0,6,0],[0,0,6]],['Na','Cl'],[1,1],[[.98,.2,.3],[.5,.5,.5]]));vectors=[[.2,.1,.05],[-.1,.3,-.1],[.15,-.15,.2],[-.2,-.1,-.05]];rows=[]
    for i,v in enumerate(vectors):
        coords=[(.98+v[0]/6)%1,.2+v[1]/6,.3+v[2]/6];f=c.asset(str(i)+'.vasp',poscar([[6,0,0],[0,6,0],[0,0,6]],['Na','Cl'],[1,1],[coords,[.5,.5,.5]]));n=c.add('displacement_'+str(i),'MatchedPeriodicDisplacements',{'reference_file':ref,'mobile_file':f});rows.append([N(n,f'/displacements/0/displacement_angstrom/{j}') for j in range(3)])
    means=[];interval=[]
    for j in range(3):
        b=c.add('bootstrap_'+str(j),'BootstrapMeanInterval',{'values':vector(*[r[j] for r in rows]),'confidence':V(.95),'resamples':V(1000),'seed':V(31)});means.append(N(b,'/mean'));interval.append(vector(N(b,'/lower'),N(b,'/upper')))
    centered=[[E('subtract',r[j],means[j]) for j in range(3)] for r in rows]
    cov=c.add('covariance','MatrixMultiply',{'left':matrix([[E('divide',r[j],V(3)) for r in centered] for j in range(3)]),'right':matrix(centered)})
    e=c.add('spectrum','SymmetricEigenDecomposition',{'values':N(cov,'/product')})
    c.out('displacements',matrix(rows),'array');c.out('means_xyz',vector(*means),'array');c.out('intervals_xyz',E('numeric_rows',*interval),'array');c.out('covariance',N(cov,'/product'),'array');c.out('spectrum',N(e,'/eigenvalues'),'array');c.out('anisotropy',E('divide',N(e,'/eigenvalues/2'),N(e,'/eigenvalues/0')))
    return c.emit()


def occupancy_confounding():
    c=Case(68,'Material','intermediate','Vacancy fraction hidden by normalized cation composition',
      'Six cubic controls vary total cation occupancy t and occupied-site K fraction f, with Cl occupancy fixed1. Report densities and parsed per-cell Na,K,Cl amounts. Train on records0,1,2,3 and hold out4,5. Fit two linear density models: f_only has feature[f]; inventory has features[actual Na amount,actual K amount]. Report predictions_f_only,predictions_inventory and their held-out RMSEs. Select all minimum-RMSE model IDs. Fraction f describes occupied cation sites, not total cation inventory. No electroneutrality, compensating defects or thermodynamic stability is inferred for these formal geometry controls.',
      {'t':[1.,1.,.8,.8,.6,.6],'f':[0.,1.,0.,1.,.25,.75]},'occupancy_normalization_confounding','The same density observations are compared under normalized-composition and actual-inventory hypotheses.',
      ['Independent mixed-occupancy structure parsing and density','Two training-only coordinate models and held-out checks'],
      'Test whether normalizing composition discards the vacancy information needed to predict mass density.')
    ds=[];inventory=[]
    for i,(t,f) in enumerate(zip(c.inputs['t'],c.inputs['f'])):
        sites=[]
        if t*(1-f)>0:sites.append(('Na',0,0,0,t*(1-f)))
        if t*f>0:sites.append(('K',0,0,0,t*f))
        sites.append(('Cl',.5,.5,.5,1))
        file=lattice_file(c,str(i),(5,5,5,90,90,90),sites);d=density(c,'density_'+str(i),file);n=composition(c,'composition_'+str(i),file);ds.append(N(d,'/density_g_per_cm3'))
        inventory.append([N(n,'/element_amounts/'+e) if (e=='Na' and f<1) or (e=='K' and f>0) or e=='Cl' else V(0.) for e in ['Na','K','Cl']])
    c.out('densities',vector(*ds),'array');c.out('amounts_Na_K_Cl',matrix(inventory),'array');errors=[]
    for tag,features in [('f_only',[[I(f'/f/{i}')] for i in range(6)]),('inventory',[r[:2] for r in inventory])]:
        fit=c.add('fit_'+tag,'FitLinearRegression',{'training_features':matrix(features[:4]),'targets':vector(*ds[:4])});p=c.add('pred_'+tag,'PredictLinearModel',{'model':N(fit,'/model'),'features':matrix(features[4:])});m=c.add('error_'+tag,'RegressionMetrics',{'truth':vector(*ds[4:]),'predicted':N(p,'/predictions')});c.out('predictions_'+tag,N(p,'/predictions'),'array');c.out('rmse_'+tag,N(m,'/rmse'));errors.append(N(m,'/rmse'))
    c.selection('selected',['f_only','inventory'],errors);return c.emit()




def label_inventory():
    c=Case(69,'Material','intermediate','Formula labels versus actual supplied-cell inventories',
      'Three geometry files have table labels declared_formula. For each a,b,c report actual_counts [Na,K,Cl], declared_counts [Na,K,Cl], actual_atom_fractions and declared_atom_fractions in that element order; absent elements are exact zeros. Determine label_consistent_a etc. by equality of the FULL atomic-fraction vectors within1e-9, so an unreduced formula can be consistent. Independently report density_a etc. (g/cm^3) and supplied_cell_atoms_a etc. from the source cell. A matching element set alone does not validate a formula ratio, and an unreduced label is not a defective cell.',
      {'declared_formula':['Na2Cl2','NaCl','NaCl2']},'formula_label_source_audit','Each original cell identity anchors stoichiometry and independent density/site-count evidence.',
      ['Declared-formula and actual-cell composition branches','Independent density and atom inventory witnesses'],
      'Separate harmless formula scaling from wrong chemical species or wrong stoichiometric ratios.')
    actual_names=[('Na','Cl'),('K','Cl'),('Na','Cl')]
    from pymatgen.core import Composition
    for i,k in enumerate('abc'):
        file=lattice_file(c,k,*rock([5.64,6.29,5.2][i],*actual_names[i]));a=composition(c,'actual_'+k,file);d=density(c,'density_'+k,file);f=c.add('declared_'+k,'CompositionFractions',{'formula':I(f'/declared_formula/{i}')})
        observed=[];declared=[]
        for e in ['Na','K','Cl']:
            observed.append(N(a,'/element_amounts/'+e) if e in actual_names[i] else V(0.))
            declared.append(N(f,'/element_amounts/'+e) if e in Composition(c.inputs['declared_formula'][i]) else V(0.))
        total=E('sum',vector(*observed));dtotal=E('sum',vector(*declared));af=vector(*[E('divide',v,total) for v in observed]);df=vector(*[E('divide',v,dtotal) for v in declared])
        for name,value in [('actual_counts',vector(*observed)),('declared_counts',vector(*declared)),('actual_atom_fractions',af),('declared_atom_fractions',df)]:c.out(name+'_'+k,value,'array')
        c.flag('label_consistent_'+k,af,'eq',df);c.out('density_'+k,N(d,'/density_g_per_cm3'));c.out('supplied_cell_atoms_'+k,N(d,'/sites'))
    return c.emit()


def qchem_source(c):
    import gzip,hashlib
    root=Path(__file__).resolve().parents[5]
    origin=root/'tasks/full/assets/6.1.1.freq.out.gz';text=gzip.decompress(origin.read_bytes()).decode('latin1')
    file=c.asset('water_source.qout',text)
    c.inputs['source']=file['value']
    return file,{'basis':'Bundled public completed Q-Chem water fixture, decompressed without text edits; not a new calculation.','original_relative_path':'tasks/full/assets/6.1.1.freq.out.gz','original_compressed_sha256':hashlib.sha256(origin.read_bytes()).hexdigest()}


def mode_metrics():
    c=Case(70,'Material','intermediate','Normal-mode vector metric and IR-column alignment audit',
      'Use the bundled completed water Q-Chem source without inventing a new calculation. Read the three mode displacement tensors, three frequencies and three IR intensities in printed mode order. Flatten each mode in [atom0 x,y,z,atom1 x,y,z,atom2 x,y,z] order into M(3x9). Report frequencies,ir_intensities,plain_gram=M M^T, and weighted_gram=(M D)(M D)^T with D=diag(4,4,4,1,1,1,1,1,1). These explicitly declared metric weights use O:H=16:1 as a model convention. Report ascending spectra plain_spectrum,weighted_spectrum, and intensity_fractions = intensities/sum(intensities). Do not assume printed rounded displacement vectors are orthonormal in either metric.',
      {},'normal_mode_metric_audit','One immutable mode/IR source and printed column/atom order.',
      ['Source mode, frequency and intensity parsing','Unweighted versus declared mass-metric Gram matrices and spectra'],
      'Check metric and column identity before using displacement normalization or IR magnitudes.',
      'The bundled source is reused as a fixed computational record; this exercise does not run quantum chemistry or assign a Materials Project identity.')
    f,provenance=qchem_source(c);m=c.add('modes','ReadQChemFrequencyModes',{'qchem_file':I('/source')});freq=c.add('freq','GetMolecularFrequencies',{'qchem_file':I('/source')});ir=c.add('ir','ReadQChemIRIntensities',{'qchem_file':I('/source')})
    M=matrix([[N(m,f'/value/{i}/{a}/{j}') for a in range(3) for j in range(3)] for i in range(3)]);Mt=matrix([[N(m,f'/value/{i}/{a}/{j}') for i in range(3)] for a in range(3) for j in range(3)])
    g=c.add('plain','MatrixMultiply',{'left':M,'right':Mt});weighted_rows=[[E('multiply',N(m,f'/value/{i}/{a}/{j}'),V(4 if a==0 else 1)) for a in range(3) for j in range(3)] for i in range(3)];Mw=matrix(weighted_rows);Mwt=matrix([[weighted_rows[i][j] for i in range(3)] for j in range(9)]);wg=c.add('weighted_gram','MatrixMultiply',{'left':Mw,'right':Mwt})
    for label,node in [('plain',g),('weighted',wg)]:
        e=c.add(label+'_spectrum','SymmetricEigenDecomposition',{'values':N(node,'/product')});c.out(label+'_gram',N(node,'/product'),'array');c.out(label+'_spectrum',N(e,'/eigenvalues'),'array')
    c.out('frequencies',N(freq,'/value'),'array');c.out('ir_intensities',N(ir,'/value'),'array');c.out('intensity_fractions',vector(*[E('divide',N(ir,f'/value/{i}'),E('sum',N(ir,'/value'))) for i in range(3)]),'array')
    row=c.emit();row['asset_provenance']={f['value'][8:]:provenance};return row


def reservoir_thermodynamics():
    c=Case(71,'Material','intermediate','Shared molecular reservoir correction across pressure and surface states',
      'Three hypothetical water-binding surface states have electronic adsorption energies delta_e_eV per water, already defined relative to the gas electronic energy. Read water translational,rotational,vibrational ENTHALPY (kcal/mol) and ENTROPY (cal/(mol K)) from the supplied298.15K source. Report H_parts,S_parts,H_eV,S_eV_per_K and mu0_thermal=H_eV-T*S_eV_per_K, using1kcal=4184J and1eV per molecule=96485.33212331002J/mol. The printed vibrational enthalpy already contains its zero-point contribution: do not add it again. For pressure ratios[0.001,1,1000] relative to1atm report delta_g as a3x3 array (pressure rows,state columns): delta_e-mu0_thermal-k_B*T*ln(p/p0), k_B=8.617333262145e-5eV/K. Report favorable with the same shape as booleans delta_g<0. Adsorbed-state thermal corrections are explicitly neglected in this toy model.',
      {'delta_e_eV':[-.05,.1,.25],'pressure_ratios':[.001,1.,1000.],'temperature':298.15},'shared_reservoir_pressure_free_energy','One source-consistent thermal reservoir correction is shared by every pressure and surface state.',
      ['Six independently parsed thermal components','Pressure logarithms and the electronic-state panel'],
      'Combine units and standard-state conventions once, then evaluate the complete declared condition table.',
      'Hypothetical surface energies and an explicitly simplified reservoir model; no real surface stability or experimental adsorption prediction.')
    f,provenance=qchem_source(c);hs=[];ss=[]
    for label,part in [('trans','Translational'),('rot','Rotational'),('vib','Vibrational')]:
        h=c.add('h_'+label,'ReadQChem'+part+'Enthalpy',{'qchem_file':I('/source')});s=c.add('s_'+label,'ReadQChem'+part+'Entropy',{'qchem_file':I('/source')});hs.append(N(h,'/value'));ss.append(N(s,'/value'))
    H=E('multiply',V(4184/96485.33212331002),E('sum',vector(*hs)));S=E('multiply',V(4.184/96485.33212331002),E('sum',vector(*ss)));mu=E('subtract',H,E('multiply',I('/temperature'),S));ln=c.add('logp','ElementwiseNumericOperations',{'operation':V('log'),'values':I('/pressure_ratios')})
    rows=[]
    for i in range(3):
        rows.append([E('subtract',E('subtract',I(f'/delta_e_eV/{j}'),mu),E('multiply',V(8.617333262145e-5),E('multiply',I('/temperature'),N(ln,f'/values/{i}')))) for j in range(3)])
    for key,target in [('H_parts',vector(*hs)),('S_parts',vector(*ss)),('H_eV',H),('S_eV_per_K',S),('mu0_thermal',mu),('delta_g',matrix(rows))]:c.out(key,target,'array' if key in ['H_parts','S_parts','delta_g'] else 'number')
    # Scalar flags retain both true and false boundary evidence without Boolean-to-number coercion.
    for i in range(3):
        for j in range(3):c.flag(f'favorable_{i}_{j}',rows[i][j],'lt',V(0))
    c.question=c.question.replace('Report favorable with the same shape as booleans delta_g<0.','Report favorable_i_j boolean fields for pressure row i and state column j (0-based), using delta_g<0.')
    row=c.emit();row['asset_provenance']={f['value'][8:]:provenance};return row


def spectral_unmixing():
    c=Case(72,'Material','advanced','Mode-aligned instrument templates and spectral mixture identifiability',
      'The completed source supplies three water vibrational frequencies and IR intensities, which define initial template identities. Each band has its OWN supplied five-point instrument calibration curve. Fit each with gaussian_peak(height,center,width), initial=[printed intensity,printed frequency,15], bounds height[0,10000],center[printed frequency-10,printed frequency+10],width[1,100], linear loss and max_evaluations2000. Report fitted parameters parameters_a,b,c. Evaluate all three fitted bands on the common measurement_x. Form a design matrix with columns[band a,band b,band c,1,(x-2500)/1000]; report singular_values and solve ordinary least squares against measurement_y for coefficients. Report predicted and rmse from an independent forward multiplication and metric. Do not equate source IR intensity with a measured mixture coefficient or silently permute mode identities.',
      {},'mode_aligned_spectral_inverse','Printed mode identities anchor three calibration fits; their common measurement grid is the shared inverse-design row domain.',
      ['Independent calibrated band fits/evaluations','Design singular spectrum versus least-squares mixture inference and forward residual validation'],
      'Separate source mode strength, instrument response, mixture coefficients and nuisance baseline identifiability.',
      'Instrument curves and measured mixture are synthetic controls; the bundled source is a fixed record, not a newly executed quantum calculation.')
    import math
    f,provenance=qchem_source(c);freqs=[1590.33,3884.52,3980.89];intens=[106.754,26.209,128.758];grid=[f+o for f in freqs for o in [-35,-15,0,15,35]]
    c.inputs.update(calibration_x=[[f+o for o in [-30,-15,0,15,30]] for f in freqs],calibration_y=[[a*math.exp(-.5*(o/20)**2) for o in [-30,-15,0,15,30]] for a in intens],measurement_x=grid,measurement_y=[sum(w*a*math.exp(-.5*((x-f)/20)**2) for w,a,f in zip([.4,.9,1.3],intens,freqs))+.1+.03*(x-2500)/1000 for x in grid])
    fr=c.add('frequencies','GetMolecularFrequencies',{'qchem_file':I('/source')});ir=c.add('intensities','ReadQChemIRIntensities',{'qchem_file':I('/source')});bands=[]
    for i,k in enumerate('abc'):
        fit=c.add('fit_'+k,'FitParametricCurve',{'x':I(f'/calibration_x/{i}'),'y':I(f'/calibration_y/{i}'),'model_type':V('gaussian_peak'),'initial_parameters':vector(N(ir,f'/value/{i}'),N(fr,f'/value/{i}'),V(15)),'lower_bounds':vector(V(0),E('subtract',N(fr,f'/value/{i}'),V(10)),V(1)),'upper_bounds':vector(V(10000),E('add',N(fr,f'/value/{i}'),V(10)),V(100)),'loss':V('linear'),'max_evaluations':V(2000)});ev=c.add('evaluate_'+k,'EvaluateParametricCurve',{'model':N(fit,'/model'),'x':I('/measurement_x')});bands.append(ev);c.out('parameters_'+k,N(fit,'/model/parameters'),'array')
    A=matrix([[N(n,f'/predictions/{i}') for n in bands]+[V(1),E('divide',E('subtract',I(f'/measurement_x/{i}'),V(2500)),V(1000))] for i in range(len(grid))]);svd=c.add('spectrum','MatrixSVD',{'values':A});solve=c.add('mixture','LinearLeastSquares',{'matrix_a':A,'vector_b':I('/measurement_y')});pred=c.add('forward','MatrixMultiply',{'left':A,'right':N(solve,'/solution')});metric=c.add('error','RegressionMetrics',{'truth':I('/measurement_y'),'predicted':N(pred,'/product')})
    c.out('singular_values',N(svd,'/singular_values'),'array');c.out('coefficients',N(solve,'/solution'),'array');c.out('predicted',N(pred,'/product'),'array');c.out('rmse',N(metric,'/rmse'))
    row=c.emit();row['asset_provenance']={f['value'][8:]:provenance};return row


def oxygen_packing():
    c=Case(74,'Material','foundation','Anion packing versus total mass-density ranking',
      'Four oxide geometry controls contain the stated actual cell inventories. For each a,b,c,d report total_density_a etc. (g/cm^3), oxygen_count_a etc. and volume_a etc. (A^3). Report oxygen_number_density_a etc.=oxygen_count/volume and oxygen_mass_fraction_a etc. from the supplied formula. Independently report oxygen_mass_density_a etc.=total_density*oxygen_mass_fraction. Return densest_ids by total density and oxygen_packed_ids by oxygen number density, retaining ties. Do not use a reduced formula atom count as the actual supplied-cell count or interpret static packing as measured transport.',
      {'formula':['MgO','CaO','TiO2','Al2O3']},'anion_number_vs_mass_packing','Actual-cell source identities and formula fractions anchor two distinct physical density definitions.',
      ['Independent structure density/element inventories','Formula mass fractions and post-measurement oxygen normalization'],
      'Collect two rankings under declared physical units instead of treating heavy cations as greater oxygen packing.')
    panels=[((4.2,4.2,4.2,90,90,90),[('Mg',0,0,0),('O',.5,.5,.5)]),((4.8,4.8,4.8,90,90,90),[('Ca',0,0,0),('O',.5,.5,.5)]),((4.6,4.6,3,90,90,90),[('Ti',0,0,0),('O',.3,.3,0),('O',.7,.7,.5)]),((4.8,4.8,5,90,90,90),[('Al',0,0,0),('Al',.5,.5,.5),('O',.3,0,.2),('O',0,.3,.4),('O',.7,.7,.8)])];densities=[];numbers=[]
    for i,k in enumerate('abcd'):
        f=lattice_file(c,k,*panels[i]);d=density(c,'density_'+k,f);n=composition(c,'count_'+k,f);a=c.add('fraction_'+k,'CompositionFractions',{'formula':I(f'/formula/{i}')});rho=N(d,'/density_g_per_cm3');v=N(d,'/volume_angstrom_cubed');count=N(n,'/element_amounts/O');number=E('divide',count,v);fraction=N(a,'/mass_fractions/O');densities.append(rho);numbers.append(number)
        for key,value in [('total_density',rho),('oxygen_count',count),('volume',v),('oxygen_number_density',number),('oxygen_mass_fraction',fraction),('oxygen_mass_density',E('multiply',rho,fraction))]:c.out(key+'_'+k,value)
    c.selection('densest_ids',list('abcd'),densities,maximize=True);c.selection('oxygen_packed_ids',list('abcd'),numbers,maximize=True);return c.emit()




def nbo_spin():
    c=Case(73,'Material','foundation','Population-accounting audit across three supplied records',
      'Three controlled transcription-audit records a,b,c share atom order[Mg,O,C,C] and nuclear charges[12,8,6,6]. Treat them as independent inputs. Identify combined,alpha,beta channels from printed metadata. For each k report electron_totals_k in that channel order,charge_residual_k=abs(32-sum(combined Total)-sum(combined Charge)),spin_residual_k=max_atom abs(alpha Total-beta Total-combined Density),and component_residual_k=max_atom abs(Core+Valence+Rydberg-combined Total). accounting_residual_k is the maximum of these three residuals; consistent_k means it is<=5e-5. Report largest_violation_ids,all record IDs attaining the largest accounting residual,with absolute tie tolerance1e-9. Preserve source values and channel identity; do not repair an inconsistent record or combine populations across records.',
      {},'independent_population_transcription_audit','The declared atom identity and accounting definitions are common; each record retains its own immutable evidence.',
      ['Three independent source/channel audits','Charge,spin and population-decomposition evidence within each source'],
      'Compare violations only after preserving independent record identities and the same printed-precision tolerance.',
      'Controlled transcription-audit fixtures derived from one bundled output,not three physical electronic states or new quantum calculations.')
    import hashlib
    root=Path(__file__).resolve().parents[5];origin=root/'tasks/full/assets/nbo7_1.qout';raw=origin.read_text()
    substitutions=[None,('11.23143     0.81608','11.23143     0.91608'),
      ('9.99982     1.04323    0.18838    11.23143','9.99982     1.04323    0.38838    11.23143')]
    header='SCITOOLFLOW CONTROLLED TRANSCRIPTION-AUDIT FIXTURE. Numerical table consistency is unverified. Not a new quantum calculation.\n'
    residuals=[];provenance={}
    for i,k in enumerate('abc'):
        content=raw
        if substitutions[i]:
            old,new=substitutions[i];assert raw.count(old)==1
            content=raw.replace(old,new,1)
        file=c.asset('record_'+k+'.qout',header+content);c.inputs.setdefault('sources',[]).append(file['value'])
        provenance[file['value'][8:]]={'basis':'Controlled transcription-audit fixture derived from a bundled completed output. Values require an independent accounting audit; not a distinct physical state or newly run calculation.',
          'original_relative_path':'tasks/full/assets/nbo7_1.qout','original_sha256':hashlib.sha256(origin.read_bytes()).hexdigest()}
        n=c.add('record_'+k,'ReadQChemNBOPopulations',{'qchem_file':I(f'/sources/{i}')})
        c.nodes[-1]['alternatives'][0]['output_rules'] += [{'path':f'/value/table_context/{h}/spin_channel','op':'eq','value':channel} for h,channel in enumerate(['combined','alpha','beta'])]
        def pop(channel,column,j):return N(n,f'/value/natural_population_tables/{channel}/{column}/{j}')
        totals=[E('sum',vector(*[pop(h,'Total',j) for j in range(4)])) for h in range(3)]
        charge=E('abs',E('subtract',E('subtract',V(32),totals[0]),E('sum',vector(*[pop(0,'Charge',j) for j in range(4)]))))
        spin=E('max',vector(*[E('abs',E('subtract',E('subtract',pop(1,'Total',j),pop(2,'Total',j)),pop(0,'Density',j))) for j in range(4)]))
        component=E('max',vector(*[E('abs',E('subtract',E('sum',vector(*[pop(0,col,j) for col in ['Core','Valence','Rydberg']])),pop(0,'Total',j))) for j in range(4)]))
        maximum=E('max',vector(charge,spin,component));residuals.append(maximum)
        c.out('electron_totals_'+k,vector(*totals),'array')
        for field,target in [('charge_residual',charge),('spin_residual',spin),('component_residual',component),('accounting_residual',maximum)]:c.out(field+'_'+k,target)
        c.flag('consistent_'+k,maximum,'le',V(5e-5))
    c.selection('largest_violation_ids',list('abc'),residuals,maximize=True)
    row=c.emit();row['asset_provenance']=provenance;return row


def build():return [phase_unmixing(),density_model(),cutoff_envelope(),diffraction_nuisance(),periodic_replicates(),occupancy_confounding(),label_inventory(),mode_metrics(),reservoir_thermodynamics(),spectral_unmixing(),nbo_spin(),oxygen_packing()]
