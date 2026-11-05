"""Thirteen explicit numerical research workflows with substantive shared-state graphs."""
from .common import *


def temporal_validation():
    c=Case(88,'MachineLearning','advanced','Rolling temporal embargo with frozen per-cutoff feature scales',
      'Fifteen ordered measurements have times0..14. For each cutoff a=5,b=8,c=11 with gap1, train on times<=cutoff and test only times>cutoff+1; report train_k,test_k,gap_k. Fit population feature standardization using that cutoff TRAINING rows only, apply it to training and test separately, then fit ridge alpha1 with an unpenalized intercept on standardized training data. Report mean_k,scale_k,predictions_k and held-out rmse_k. No future or embargoed row may affect preprocessing or fitting; each cutoff starts with its own frozen scales. This finite rolling exercise does not establish temporal independence or out-of-distribution guarantees.',
      {'times':list(range(15)),'features':[[i,(i%3)-1] for i in range(15)],'targets':[.3,1.1,2.2,2.8,4.2,5.1,5.8,7.1,8.2,9.9,11.4,12.1,13.8,15.2,16.1]},
      'rolling_embargo_preprocessing','Each temporal split anchors two independent transforms sharing the same training-only scale.',
      ['Three independent cutoff workflows','Training transform/fit versus held-out transform after each frozen training population'],
      'Compare actual future errors without leaking later rows through scales or row identities.')
    for k,cut in zip('abc',[5,8,11]):
        s=c.add('split_'+k,'TimeSeriesSplitRecords',{'times':I('/times'),'cutoff':V(cut),'gap':V(1)})
        train=E('slice',I('/features'),V(0),V(cut+1));test=E('slice',I('/features'),V(cut+2),V(15));ytrain=E('slice',I('/targets'),V(0),V(cut+1));ytest=E('slice',I('/targets'),V(cut+2),V(15))
        tr=c.add('scale_train_'+k,'StandardizeNumericFeatures',{'training_features':train,'features':train},parents=[s]);te=c.add('scale_test_'+k,'StandardizeNumericFeatures',{'training_features':train,'features':test},parents=[s]);fit=c.add('fit_'+k,'FitRidgeRegression',{'training_features':N(tr,'/features'),'targets':ytrain,'alpha':V(1.)});pred=c.add('prediction_'+k,'PredictLinearModel',{'model':N(fit,'/model'),'features':N(te,'/features')});metric=c.add('metric_'+k,'RegressionMetrics',{'truth':ytest,'predicted':N(pred,'/predictions')})
        for field,port in [('train','train_indices'),('test','test_indices'),('gap','gap_indices')]:c.out(field+'_'+k,N(s,'/'+port),'array')
        c.out('mean_'+k,N(tr,'/mean'),'array');c.out('scale_'+k,N(tr,'/scale'),'array');c.out('predictions_'+k,N(pred,'/predictions'),'array');c.out('rmse_'+k,N(metric,'/rmse'))
    return c.emit()


def truncated_inverse():
    c=Case(89,'MachineLearning','intermediate','Truncated inverse paths under residual and solution-size constraints',
      'Compute one economy SVD of A. For retained ranks r1,r2,r3=1,2,3 construct V_r diag(1/s_r) U_r^T, solve x_r with b and independently forward-check A*x_r. Report singular_values,solution_r1..r3,predicted_r1..r3,rmse_r1..r3 and norm_squared_r1..r3. Report admissible_r for BOTH RMSE<=0.02 and squared Euclidean solution norm<=9. Use complete retained subspaces; singular-vector sign changes are immaterial. A smaller residual alone does not justify noise-amplifying inverse directions.',
      {'A':[[1,1,0],[0,.1,.1],[0,0,.001]],'b':[1,.2,.003]},
      'truncated_inverse_regularization','One decomposition is shared by three rank-controlled inverse/forward-witness chains.',
      ['Three retained-rank subgraphs after the common SVD','Forward residual versus solution-size evidence within each rank'],
      'Apply two independent admissibility criteria without ranking solely by fit.')
    s=c.add('svd','MatrixSVD',{'values':I('/A')});c.out('singular_values',N(s,'/singular_values'),'array')
    for r in [1,2,3]:
        tag='r'+str(r);Vmat=matrix([[N(s,f'/vt/{h}/{j}') for h in range(r)] for j in range(3)]);D=matrix([[E('divide',V(1),N(s,f'/singular_values/{i}')) if i==j else V(0.) for j in range(r)] for i in range(r)]);Ut=matrix([[N(s,f'/u/{j}/{h}') for j in range(3)] for h in range(r)])
        scaled=matrix([[E('divide',N(s,f'/vt/{h}/{j}'),N(s,f'/singular_values/{h}')) for h in range(r)] for j in range(3)]);inverse=c.add('inverse_'+tag,'MatrixMultiply',{'left':scaled,'right':Ut});x=c.add('solution_'+tag,'MatrixMultiply',{'left':N(inverse,'/product'),'right':I('/b')});pred=c.add('forward_'+tag,'MatrixMultiply',{'left':I('/A'),'right':N(x,'/product')});m=c.add('metric_'+tag,'RegressionMetrics',{'truth':I('/b'),'predicted':N(pred,'/product')});norm=E('sum',vector(*[E('multiply',N(x,f'/product/{i}'),N(x,f'/product/{i}')) for i in range(3)]))
        c.out('solution_'+tag,N(x,'/product'),'array');c.out('predicted_'+tag,N(pred,'/product'),'array');c.out('rmse_'+tag,N(m,'/rmse'));c.out('norm_squared_'+tag,norm);margin=E('max',vector(E('divide',N(m,'/rmse'),V(.02)),E('divide',norm,V(9))));c.flag('admissible_'+tag,margin,'le',V(1))
    return c.emit()


def estimable_contrasts():
    c=Case(90,'MachineLearning','advanced','Rank-deficient coefficients can still identify particular contrasts',
      'Fit the unweighted minimum-norm least-squares system A*beta=y and independently compute an economy SVD of A. Retain right-singular directions with singular value>1e-8 and form row-space projector P. Report singular_values,rank,projector and fitted_y. For contrast rows a,b,c in C report projection_residual_squared_k=||P*c-c||^2, estimable_k iff this is<=1e-16, and estimate_k=c dot beta only for estimable contrasts; otherwise null. Do not infer a unique coefficient vector from a unique fitted response, and do not report an arbitrary minimum-norm coefficient as an identified contrast.',
      {'A':[[1,0,0],[0,1,1],[1,1,1],[2,1,1]],'y':[1,2,3,4],'C':[[1,0,0],[0,1,0],[0,1,1]]},
      'contrast_identifiability_row_space','The same design supports an independent data fit and a basis-invariant row-space witness.',
      ['Least-squares fitted-response chain','SVD projector and batched contrast-estimability chain'],
      'Separate prediction, coefficient nonuniqueness and contrast-specific scientific identifiability.')
    f=c.add('fit','LinearLeastSquares',{'matrix_a':I('/A'),'vector_b':I('/y')});s=c.add('svd','MatrixSVD',{'values':I('/A')});c.nodes[-1]['alternatives'][0]['output_rules'] += [{'path':'/singular_values/1','op':'gt','value':1e-8},{'path':'/singular_values/2','op':'le','value':1e-8}]
    V2=matrix([[N(s,f'/vt/{h}/{i}') for h in range(2)] for i in range(3)]);V2t=matrix([[N(s,f'/vt/{h}/{i}') for i in range(3)] for h in range(2)]);P=c.add('projector','MatrixMultiply',{'left':V2,'right':V2t});proj=c.add('contrasts','MatrixMultiply',{'left':N(P,'/product'),'right':V([[1,0,0],[0,1,1],[0,0,1]])});pred=c.add('forward','MatrixMultiply',{'left':I('/A'),'right':N(f,'/solution')})
    c.out('singular_values',N(s,'/singular_values'),'array');c.out('rank',N(f,'/rank'));c.out('projector',N(P,'/product'),'array');c.out('fitted_y',N(pred,'/product'),'array')
    for i,k in enumerate('abc'):
        error=E('sum',vector(*[E('multiply',E('subtract',N(proj,f'/product/{j}/{i}'),I(f'/C/{i}/{j}')),E('subtract',N(proj,f'/product/{j}/{i}'),I(f'/C/{i}/{j}'))) for j in range(3)]));c.out('projection_residual_squared_'+k,error)
        for tag,op,flag in [('yes','le',True),('no','gt',False)]:
            branch='estimable_'+k+'_'+tag;c.branches.append({'id':branch,'when':{'left':error,'op':op,'value':1e-16}});c.out('estimable_'+k,V(flag),'boolean',[proj],branch);c.out('estimate_'+k,dot([I(f'/C/{i}/{j}') for j in range(3)],[N(f,f'/solution/{j}') for j in range(3)]) if flag else V(None),['number','null'],[f,proj],branch)
    return c.emit()


def positive_label():
    c=Case(91,'MachineLearning','intermediate','A named positive class is not necessarily probability column one',
      'Fit one standardized logistic model on training data, C=1,max_iterations300. The scientific POSITIVE label is affected; healthy is negative. Report classes from the fitted model. For heldout cohorts a,b report positive_probabilities_k and Brier score brier_k, selecting the probability column by its class label, not an assumed column1. For thresholds low0.4 and high0.7 report labels_k_low/high and total_cost_k_low/high; false positives cost3,false negatives cost8. Evaluate every declared cohort/policy; do not refit, recalibrate or choose a threshold using test labels.',
      {'X':[[-2,0],[-1,1],[-1,-1],[0,-1],[0,1],[1,0],[1,1],[2,0],[-2,1],[2,1],[0,2],[1,-2]],'y':['healthy','healthy','healthy','affected','healthy','affected','healthy','affected','healthy','affected','healthy','affected'],
       'test_X':[[[-.5,0],[.5,0],[1,1],[2,-1]],[[-1,-1],[0,1],[1,0],[2,2]]],'test_y':[['healthy','affected','healthy','affected'],['healthy','healthy','affected','healthy']]},
      'class_label_probability_semantics','One class-labelled standardized model feeds two held-out probability vectors and four policy branches.',
      ['Two independent held-out predictions','Brier calibration and threshold/cost chains using the same positive-class probabilities'],
      'Preserve label meaning across probability, classification and cost interfaces.')
    f=c.add('fit','FitLogisticRegression',{'training_features':I('/X'),'targets':I('/y'),'regularization_c':V(1.),'max_iterations':V(300)});c.out('classes',N(f,'/model/classes'),'array')
    for i,k in enumerate('ab'):
        p=c.add('predict_'+k,'PredictLogisticModel',{'model':N(f,'/model'),'features':I(f'/test_X/{i}')});prob=E('column',N(p,'/probabilities'),V(0));cal=c.add('calibration_'+k,'ProbabilityCalibrationSummary',{'truth':I(f'/test_y/{i}'),'probabilities':prob,'positive_label':V('affected')});c.out('positive_probabilities_'+k,prob,'array');c.out('brier_'+k,N(cal,'/brier_score'))
        for tag,threshold in [('low',.4),('high',.7)]:
            t=c.add('threshold_'+k+'_'+tag,'ThresholdClassProbabilities',{'probabilities':prob,'threshold':V(threshold),'positive_label':V('affected'),'negative_label':V('healthy')});d=c.add('cost_'+k+'_'+tag,'DecisionCostSummary',{'truth':I(f'/test_y/{i}'),'predicted':N(t,'/predicted'),'positive_label':V('affected'),'false_positive_cost':V(3.),'false_negative_cost':V(8.)});c.out('labels_'+k+'_'+tag,N(t,'/predicted'),'array');c.out('total_cost_'+k+'_'+tag,N(d,'/total_cost'))
    return c.emit()


def repeated_rhs():
    c=Case(92,'MachineLearning','foundation','Shared inverse versus three direct right-hand-side solutions',
      'A is a fixed symmetric positive-definite numerical control; B columns are three right-hand sides. Compute one inverse and batched inverse-times-B solution matrix. Independently solve each RHS directly as vectors direct_a,b,c. Report spectrum of A,batched_solutions,forward_B=A*batched_solutions, and residual_squared_a,b,c per RHS. Report agreement_a,b,c by direct solution versus corresponding batched column within1e-6. Do not transpose RHS identity or treat an inverse residual as a guarantee of small forward error in all systems.',
      {'A':[[4,1,0],[1,3,.5],[0,.5,2]],'B':[[1,2,0],[0,1,-1],[1,0,2]]},
      'shared_factor_multi_rhs_validation','A common inverse and matrix identity support a batched route and three independent direct-solve witnesses.',
      ['Inverse and spectrum of A plus three direct solves','Batched solution and forward residual chain'],
      'Keep RHS column identities intact while reusing matrix work.')
    inv=c.add('inverse','MatrixInverse',{'values':I('/A')});e=c.add('spectrum','SymmetricEigenDecomposition',{'values':I('/A')});batch=c.add('batch','MatrixMultiply',{'left':N(inv,'/inverse'),'right':I('/B')});pred=c.add('forward','MatrixMultiply',{'left':I('/A'),'right':N(batch,'/product')})
    c.out('spectrum',N(e,'/eigenvalues'),'array');c.out('batched_solutions',N(batch,'/product'),'array');c.out('forward_B',N(pred,'/product'),'array')
    for i,k in enumerate('abc'):
        d=c.add('direct_'+k,'SolveLinearSystem',{'matrix_a':I('/A'),'vector_b':E('column',I('/B'),V(i))});col=E('column',N(batch,'/product'),V(i));c.out('direct_'+k,N(d,'/solution'),'array');c.flag('agreement_'+k,N(d,'/solution'),'eq',col,atol=1e-6);c.out('residual_squared_'+k,E('sum',vector(*[E('multiply',E('subtract',N(pred,f'/product/{j}/{i}'),I(f'/B/{j}/{i}')),E('subtract',N(pred,f'/product/{j}/{i}'),I(f'/B/{j}/{i}'))) for j in range(3)])))
    return c.emit()


def joint_signs():
    c=Case(93,'MachineLearning','intermediate','One joint sign-randomization family versus separate endpoint tests',
      'Six independent benchmark instances supply paired differences for three endpoints in D. Joint sign exchangeability across instances is stipulated, using the SAME row sign for all three endpoints. Enumerate all64 +/-1 assignments; compute null_means=signs*D/6 and each max statistic=max_j(abs(null_mean_j)/scale_j). Report max_distribution in enumeration order, observed_standardized absolute means, and critical as the61st smallest max statistic (1-based, no interpolation). Report reject_a,b,c iff observed standardized value is STRICTLY greater than critical. Independently report exact two-sided marginal p_values from paired sign tests against zero. Do not combine independent per-endpoint sign assignments into the joint null or call this BH correction.',
      {'D':[[1,2,1],[2,1,0],[1,3,-1],[3,2,1],[2,4,0],[1,1,-1]],'scales':[1,2,.5]},
      'joint_randomization_max_statistic','One shared sign-assignment matrix preserves cross-endpoint dependence.',
      ['Joint max-statistic distribution and exact marginal-test witnesses','Shared finite null feeding an explicit order-statistic decision'],
      'Respect the joint experimental unit and the chosen familywise finite-reference convention.')
    signs=c.add('signs','EnumerateSignAssignments',{'dimension':V(6),'start_index':V(0),'max_rows':V(64)});m=c.add('sums','MatrixMultiply',{'left':N(signs,'/signs'),'right':I('/D')});maxes=vector(*[E('max',vector(*[E('divide',E('abs',N(m,f'/product/{i}/{j}')),E('multiply',V(6),I(f'/scales/{j}'))) for j in range(3)])) for i in range(64)]);q=c.add('critical','SelectOrderStatistic',{'values':maxes,'rank':V(61)})
    c.out('max_distribution',maxes,'array');observed=[E('divide',E('abs',N(m,f'/product/63/{j}')),E('multiply',V(6),I(f'/scales/{j}'))) for j in range(3)];c.out('observed_standardized',vector(*observed),'array');c.out('critical',N(q,'/selected_value'));ps=[]
    for i,k in enumerate('abc'):
        t=c.add('marginal_'+k,'PairedRandomizationTest',{'sample_a':E('column',I('/D'),V(i)),'sample_b':V([0]*6),'alternative':V('two-sided')});ps.append(N(t,'/p_value'));c.flag('reject_'+k,observed[i],'gt',N(q,'/selected_value'))
    c.out('p_values',vector(*ps),'array');return c.emit()




def robust_risk():
    truth=[[0,1,2,3],[1,2,3,4],[-1,0,1,2]];offsets=[[.1,.2,2.],[.5,.5,.5],[1.,0.,.4]]
    c=Case(94,'MachineLearning','advanced','Nominal model ranking versus worst-case population-mixture risk',
      'Three fixed prediction models are evaluated in three labelled subpopulations. Report cohort_mse as model rows[a,b,c],cohort columns[1,2,3]. Nominal weights are[0.9,0.05,0.05]. Unknown deployment weights sum1 with bounds w1[0.2,0.9],w2[0.05,0.7],w3[0.05,0.6]. For each model maximize its weighted MSE over that SAME feasible weight set, reporting worst_risks and nominal_risks. Independently forward-check each optimizer weight vector against its cohort MSE row, report witness_risks, and return robust_selected and nominal_selected as all minimum-risk model IDs. Do not pool the groups before defining the uncertainty set or use a different feasible set for each model.',
      {'truth':truth,'predictions':[[[v+offsets[m][g] for v in truth[g]] for g in range(3)] for m in range(3)],'nominal':[.9,.05,.05],'bounds':[[.2,.9],[.05,.7],[.05,.6]]},
      'distributionally_robust_group_risk','A common cohort-identity matrix and feasible deployment population apply to every model.',
      ['Nine actual cohort loss estimates','Three independent worst-mixture optimizations and nominal/forward-witness branches'],
      'Compare nominal and robust decisions without confusing an optimizer witness with a unique population estimate.',
      'A finite declared uncertainty set is analyzed; no universal fairness, causal or out-of-distribution guarantee is inferred.')
    rows=[];worst=[];nominal=[];witnesses=[]
    for i,k in enumerate('abc'):
        losses=[]
        for j in range(3):n=c.add('loss_'+k+str(j),'RegressionMetrics',{'truth':I(f'/truth/{j}'),'predicted':I(f'/predictions/{i}/{j}')});losses.append(N(n,'/mse'))
        rows.append(losses);lp=c.add('worst_'+k,'SolveLinearProgram',{'objective':vector(*losses),'bounds':I('/bounds'),'equality_matrix':V([[1,1,1]]),'equality_rhs':V([1]),'direction':V('max')});w=c.add('witness_'+k,'MatrixMultiply',{'left':matrix([losses]),'right':N(lp,'/solution')});worst.append(N(lp,'/objective_value'));nominal.append(dot(losses,[I(f'/nominal/{j}') for j in range(3)]));witnesses.append(N(w,'/product/0'))
    c.out('cohort_mse',matrix(rows),'array');c.out('worst_risks',vector(*worst),'array');c.out('nominal_risks',vector(*nominal),'array');c.out('witness_risks',vector(*witnesses),'array');c.selection('robust_selected',list('abc'),worst);c.selection('nominal_selected',list('abc'),nominal);return c.emit()


def model_tabulation():
    import math
    x=list(range(7));responses=[[a*math.exp(-.5*((v-center)/width)**2)+noise[j] for j,v in enumerate(x)] for a,center,width,noise in [(2.,2.,1.,[.01,-.01,.02,0,-.01,.01,0]),(1.5,3.,1.2,[0,.01,-.01,.01,0,-.01,.01]),(3.,4.,.9,[.01,0,.01,-.01,.02,0,-.01])]]
    c=Case(95,'MachineLearning','intermediate','Fitted response tabulation error is distinct from measurement uncertainty',
      'Fit each sensor a,b,c to gaussian_peak(height,center,width) using initial[2,3,1],bounds height[0,10],center[0,6],width[0.2,3],linear loss,max_evaluations2000. Evaluate the fitted model at the integer source grid; estimate gradients with numpy.gradient edge_order1. Use those estimated knot gradients in a cubic Hermite interpolant at half-integer query times. Independently evaluate the fitted analytic model at query times. Report parameters_k,grid_prediction_k,gradient_k,hermite_k,direct_k and interpolation_rmse_k against direct values. Also trapezoid-integrate the gradient over the original grid and report closure_error_k=integrated gradient-(last fitted response-first fitted response). These are numerical tabulation diagnostics, not confidence intervals or held-out experimental validation.',
      {'x':x,'responses':responses,'query':[.5,1.5,2.5,3.5,4.5,5.5]},
      'parametric_model_vs_numerical_tabulation','One fitted model per sensor anchors its direct query branch and its gradient/interpolation branch.',
      ['Three independent response models','Analytic query evaluation versus gradient/Hermite and closure checks'],
      'Separate fitting, tabulation and quadrature errors while preserving one source model.')
    for i,k in enumerate('abc'):
        f=c.add('fit_'+k,'FitParametricCurve',{'x':I('/x'),'y':I(f'/responses/{i}'),'model_type':V('gaussian_peak'),'initial_parameters':V([2.,3.,1.]),'lower_bounds':V([0.,0.,.2]),'upper_bounds':V([10.,6.,3.]),'loss':V('linear'),'max_evaluations':V(2000)});g=f;d=c.add('direct_'+k,'EvaluateParametricCurve',{'model':N(f,'/model'),'x':I('/query')});grad=c.add('gradient_'+k,'FiniteDifferenceGradient',{'x':I('/x'),'y':N(g,'/predictions')});h=c.add('hermite_'+k,'CubicHermiteInterpolate',{'x':I('/x'),'y':N(g,'/predictions'),'derivatives':N(grad,'/gradient'),'query_x':I('/query')});integral=c.add('integral_'+k,'NumericalTrapezoidIntegration',{'x':I('/x'),'y':N(grad,'/gradient')});error=c.add('error_'+k,'RegressionMetrics',{'truth':N(d,'/predictions'),'predicted':N(h,'/values')})
        for field,value in [('parameters',N(f,'/model/parameters')),('grid_prediction',N(g,'/predictions')),('gradient',N(grad,'/gradient')),('hermite',N(h,'/values')),('direct',N(d,'/predictions'))]:c.out(field+'_'+k,value,'array')
        c.out('interpolation_rmse_'+k,N(error,'/rmse'));c.out('closure_error_'+k,E('subtract',N(integral,'/integral'),E('subtract',N(g,'/predictions/6'),N(g,'/predictions/0'))))
    return c.emit()


def correlation_cohorts():
    rows=[]
    for x in [-1,0,1]:rows.append({'x':x,'y':x,'z':None})
    for x in [-1,0,1]:rows.append({'x':x,'y':None,'z':x})
    for x in [-1,0,1]:rows.append({'x':None,'y':x,'z':-x})
    for x in [-1,0,1]:rows.append({'x':x,'y':x,'z':x})
    c=Case(96,'MachineLearning','foundation','Pairwise-complete correlations need not form an admissible joint matrix',
      'Rows contain explicit nulls. Build two3x3 correlation matrices in[x,y,z] order with exact unit diagonals: pairwise uses each pair-specific complete-case cohort; joint uses only rows complete on ALL three fields for every pair. Report pairwise_counts and joint_counts in pair order[xy,xz,yz],correlation_pairwise,correlation_joint,ascending eigen_pairwise,eigen_joint. Report psd_pairwise and psd_joint iff smallest eigenvalue>=-1e-8. Do not replace missing values by zero, silently project to PSD or claim singular PSD matrices are invertible.',
      {'rows':rows},'pairwise_cohort_covariance_admissibility','The row table and variable identities anchor distinct pairwise and common-cohort constructions.',
      ['Six explicitly scoped pair correlations','Two independently assembled matrix spectra/admissibility checks'],
      'Expose the difference between individually valid correlations and a valid joint correlation model.')
    for mode in ['pairwise','joint']:
        counts=[];corr={}
        for a,b in [('x','y'),('x','z'),('y','z')]:
            cohort=E('records_nonnull',I('/rows'),V([a,b] if mode=='pairwise' else ['x','y','z']));data=E('records_columns',cohort,V([a,b]));n=c.add(mode+'_'+a+b,'PearsonCorrelation',{'x':E('column',data,V(0)),'y':E('column',data,V(1))});counts.append(N(n,'/count'));corr[a,b]=corr[b,a]=N(n,'/correlation')
        R=matrix([[V(1.) if a==b else corr[a,b] for b in ['x','y','z']] for a in ['x','y','z']]);e=c.add('eigen_'+mode,'SymmetricEigenDecomposition',{'values':R});c.out(mode+'_counts',vector(*counts),'array');c.out('correlation_'+mode,R,'array');c.out('eigen_'+mode,N(e,'/eigenvalues'),'array');c.flag('psd_'+mode,N(e,'/eigenvalues/0'),'ge',V(-1e-8))
    return c.emit()


def noise_coverage():
    c=Case(97,'MachineLearning','intermediate','Density-clustering quality must retain its noise-coverage domain',
      'Fit Euclidean DBSCAN with min_samples2 for eps a=0.12,b=0.35,c=10 on the supplied rows. Report labels_a,b,c (numeric-1 is noise),cluster_count_a,b,c and retained_fraction_a,b,c=(n-noise_count)/n. For any result with at least2 nonnoise clusters report silhouette_k using ClusteringQualityMetrics,otherwise null. Return raw_best as all maximum-silhouette model IDs among defined qualities, and coverage_best among defined qualities with retained_fraction>=0.8. No defined eligible result means an empty ID list. Arbitrary renaming of nonnoise cluster IDs is acceptable if partitions and noise positions are unchanged; a high silhouette on a different retained population is not automatically a better deployment model.',
      {'features':[[0,0],[.1,0],[.05,.08],[.2,.1],[3,3],[3.1,3],[3.05,3.08],[3.2,3.1],[10,10]]},
      'clustering_quality_coverage_domain','One immutable object order supports three density partitions and explicitly qualified quality summaries.',
      ['Three independent density fits','Per-fit noise/cluster-domain checks and eligible quality evaluation'],
      'Keep undefined metrics, label invariance and the retained-object population distinct.')
    raw_scores=[];coverage_scores=[]
    for k,eps in [('a',.12),('b',.35),('c',10.)]:
        d=c.add('cluster_'+k,'DBSCANClustering',{'features':I('/features'),'eps':V(eps),'min_samples':V(2)})
        coverage=E('divide',E('subtract',V(9),N(d,'/noise_count')),V(9))
        branch=c.branch('defined_'+k,d,'/cluster_count','ge',2);other=c.branch('undefined_'+k,d,'/cluster_count','lt',2)
        q=c.add('quality_'+k,'ClusteringQualityMetrics',{'features':I('/features'),'labels':N(d,'/labels')},branch=branch,parents=[d])
        c.out('labels_'+k,N(d,'/labels'),'array');out=c.outcomes[-1];out['left']=E('partition_profile',out['left'],V(True));out['right']=E('partition_profile',N(d,'/labels'),V(True))
        c.out('cluster_count_'+k,N(d,'/cluster_count'));c.out('retained_fraction_'+k,coverage)
        c.out('silhouette_'+k,N(q,'/silhouette'),['number','null'],[d,q],branch);c.out('silhouette_'+k,V(None),['number','null'],[d],other)
        raw=E('select_if_boolean',E('finite_ge',N(d,'/cluster_count'),V(2)),N(q,'/silhouette'),V(-2.))
        covered=E('select_if_boolean',E('finite_ge',coverage,V(.8)),raw,V(-2.));raw_scores.append(raw);coverage_scores.append(covered)
    # This fixture has two defined models and at least one covered model; the sentinel cannot win.
    c.selection('raw_best',list('abc'),raw_scores,maximize=True,evidence=['cluster_'+k for k in 'abc']);c.selection('coverage_best',list('abc'),coverage_scores,maximize=True,evidence=['cluster_'+k for k in 'abc']);return c.emit()


def markov_shared_powers():
    c=Case(98,'MachineLearning','intermediate','Shared Markov powers across initial populations and a stationary witness',
      'P is row-stochastic. Compute and report P2,P4,P8,P16 by shared repeated squaring. For initial ROW distributions a,b,c report dist4_k=initial*P4,dist16_k=initial*P16 and l1_to_stationary_k at horizon16. Independently solve the first two equations of(P^T-I)pi=0 plus sum(pi)=1 for stationary, and report stationary_check=pi^T*P as a row vector. Do not transpose a distribution convention, refit transitions or claim horizon16 proves a mixing-time bound.',
      {'P':[[.7,.2,.1],[.1,.7,.2],[.2,.1,.7]],'initial':[[1,0,0],[0,1,0],[.2,.3,.5]]},
      'multi_initial_shared_transition_powers','Four powers are computed once and shared by two batched forecast horizons.',
      ['Stationary-balance solve and power construction','Two batched horizon propagations, each retaining three initial-condition rows'],
      'Compare finite forecasts to a separately validated stationary distribution without recomputing common transition work.')
    prev=I('/P');nodes={}
    for p in [2,4,8,16]:n=c.add('P'+str(p),'MatrixMultiply',{'left':prev,'right':prev});prev=N(n,'/product');nodes[p]=n;c.out('P'+str(p),prev,'array')
    A=matrix([[E('subtract',I(f'/P/{j}/{i}'),V(float(i==j))) for j in range(3)] for i in range(2)]+[[V(1.)]*3]);s=c.add('stationary','SolveLinearSystem',{'matrix_a':A,'vector_b':V([0,0,1])});check=c.add('stationary_check','MatrixMultiply',{'left':matrix([[N(s,f'/solution/{j}') for j in range(3)]]),'right':I('/P')});c.out('stationary',N(s,'/solution'),'array');c.out('stationary_check',N(check,'/product/0'),'array')
    distributions={p:c.add('distributions'+str(p),'MatrixMultiply',{'left':I('/initial'),'right':N(nodes[p],'/product')}) for p in [4,16]}
    for i,k in enumerate('abc'):
        for p in [4,16]:
            n=distributions[p];c.out('dist'+str(p)+'_'+k,N(n,f'/product/{i}'),'array')
            if p==16:c.out('l1_to_stationary_'+k,E('sum',vector(*[E('abs',E('subtract',N(n,f'/product/{i}/{j}'),N(s,f'/solution/{j}'))) for j in range(3)])))
    return c.emit()


def bounded_bias():
    c=Case(99,'MachineLearning','advanced','Joint calibration uncertainty is not a Cartesian product of marginal bounds',
      'Unknown signal s and additive bias b obey0<=s,b<=8,9.8<=s+b<=10.2,and13.7<=2s+b<=14.3. For queries a=s,b=b,c=s+b report exact feasible bounds bounds_a,b,c using separate continuous LP minima/maxima over the SAME polytope. Independently compute its2D halfspace vertices and report vertices (any row order),area,and vertex_bounds_a,b,c by projecting every actual vertex onto those queries. Report sum_of_marginal_widths=width(s)+width(b) and joint_sum_width=width(s+b). Do not combine a maximum s and maximum b from different feasible points or call deterministic tolerance bounds statistical confidence intervals.',
      {'normals':[[-1,0],[1,0],[0,-1],[0,1],[1,1],[-1,-1],[2,1],[-2,-1]],'offsets':[0,8,0,8,10.2,-9.8,14.3,-13.7],'queries':[[1,0],[0,1],[1,1]]},
      'joint_set_identification_bounds','One common physical feasible set supports six extrema and a separate geometric certificate.',
      ['Six independent contrast LPs','Halfspace geometry followed by joint vertex projections'],
      'Validate marginal and joint uncertainty while preserving feasible-point dependence.')
    geometry=c.add('geometry','ConvexHalfspaceGeometry',{'normals':I('/normals'),'offsets':I('/offsets')});v=c.add('vertex_projection','MatrixMultiply',{'left':N(geometry,'/vertices'),'right':V([[1,0,1],[0,1,1]])});c.nodes[-1]['alternatives'][0]['input_rules'][0]['op']='multiset_equal'
    c.out('vertices',N(geometry,'/vertices'),'array');c.outcomes[-1]['op']='multiset_equal';c.out('area',N(geometry,'/measure'));widths=[]
    for i,k in enumerate('abc'):
        ns=[]
        for direction in ['minimize','maximize']:
            n=c.add(direction+'_'+k,'SolveLinearProgram',{'objective':I(f'/queries/{i}'),'bounds':V([[0,8],[0,8]]),'inequality_matrix':I('/normals'),'inequality_rhs':I('/offsets'),'direction':V({'minimize':'min','maximize':'max'}.get(direction,direction))});ns.append(n)
        c.out('bounds_'+k,vector(N(ns[0],'/objective_value'),N(ns[1],'/objective_value')),'array');vals=vector(*[N(v,f'/product/{j}/{i}') for j in range(4)]);c.out('vertex_bounds_'+k,vector(E('min',vals),E('max',vals)),'array');widths.append(E('subtract',N(ns[1],'/objective_value'),N(ns[0],'/objective_value')))
    c.out('sum_of_marginal_widths',E('add',widths[0],widths[1]));c.out('joint_sum_width',widths[2]);return c.emit()


def smoothing_conservation():
    c=Case(100,'MachineLearning','foundation','A shared graph smoother conserves discrete mass but not arbitrary quadrature',
      'Three response signals share a five-node path graph and a NONUNIFORM physical grid. Build unnormalized L and H=exp(-0.4L) once. Report smoothed=H*signals with signals as columns. For each a,b,c report raw_sum,smoothed_sum,raw_integral,smoothed_integral (trapezoidal on x),and gradient of the smoothed signal (numpy.gradient edge_order1). Report sum_preserved_k iff absolute raw-smoothed sum difference<=1e-8. The unweighted graph operator does not account for nonuniform physical spacings: discrete sum conservation is not conservation of the physical-grid integral or proof of a PDE model.',
      {'adjacency':[[0,1,0,0,0],[1,0,1,0,0],[0,1,0,1,0],[0,0,1,0,1],[0,0,0,1,0]],'x':[0,.5,1.5,3,4],'signals':[[1,0,2],[0,1,1],[2,0,0],[0,2,1],[1,0,3]]},
      'discrete_vs_quadrature_conservation','One graph generator and exponential operator are shared by all signals and downstream diagnostics.',
      ['Raw-signal quadratures while the common kernel is built','Three smoothed gradients and quadratures after one batched propagation'],
      'Check the correct conserved quantity instead of carrying a discrete invariant into a different physical weighting.')
    l=c.add('lap','GraphLaplacian',{'adjacency':I('/adjacency')});M=matrix([[E('multiply',V(-.4),N(l,f'/laplacian/{i}/{j}')) for j in range(5)] for i in range(5)]);h=c.add('kernel','MatrixExponential',{'values':M});s=c.add('smooth','MatrixMultiply',{'left':N(h,'/exponential'),'right':I('/signals')});c.out('smoothed',N(s,'/product'),'array')
    for i,k in enumerate('abc'):
        raw=E('column',I('/signals'),V(i));smooth=E('column',N(s,'/product'),V(i));ri=c.add('raw_integral_'+k,'NumericalTrapezoidIntegration',{'x':I('/x'),'y':raw});si=c.add('smoothed_integral_'+k,'NumericalTrapezoidIntegration',{'x':I('/x'),'y':smooth});g=c.add('gradient_'+k,'FiniteDifferenceGradient',{'x':I('/x'),'y':smooth});rs=E('sum',raw);ss=E('sum',smooth)
        for key,value,typ in [('raw_sum',rs,'number'),('smoothed_sum',ss,'number'),('raw_integral',N(ri,'/integral'),'number'),('smoothed_integral',N(si,'/integral'),'number'),('gradient',N(g,'/gradient'),'array')]:c.out(key+'_'+k,value,typ,evidence=[ri] if key=='raw_sum' else None)
        c.flag('sum_preserved_'+k,E('abs',E('subtract',rs,ss)),'le',V(1e-8))
    return c.emit()


def build():return [temporal_validation(),truncated_inverse(),estimable_contrasts(),positive_label(),repeated_rhs(),joint_signs(),robust_risk(),model_tabulation(),correlation_cohorts(),noise_coverage(),markov_shared_powers(),bounded_bias(),smoothing_conservation()]
