"""Finite, source-pinned numerical research studies, with observation-bound grading.

PREFLIGHT_PLANS are author-only executable tool-contract recipes, never public
reference trajectories or numerical answer keys.
"""
import json
from evaluation.workflow.schema import validate_workflow

PREFLIGHT_PLANS={}
def V(x): return {'value':x}
def I(p): return {'source':'inputs','path':p}
def N(n,p=''):return {'source':'node','node':n,'path':p}
def E(name,*args,**kw):return {'operation':name,'args':list(args),**kw}
def refs(x):
    if isinstance(x,dict):
        if x.get('source')=='node':yield x['node']
        for y in x.values():yield from refs(y)
    elif isinstance(x,list):
        for y in x:yield from refs(y)

class Study:
    def __init__(self,num,title,question,inputs,strong=False,units='All inputs and outputs are dimensionless unless explicitly stated.'):
        self.id=f'SMAS-{num:04d}';self.title=title;self.question=question;self.inputs=inputs;self.strong=strong;self.units=units
        self.nodes=[];self.outcomes=[];self.branches=[];self.properties={};self.plan=[]
    def add(self,n,tool,args,checks=None,parents=(),branch=None):
        deps=sorted(set(parents)|set(refs(args)))
        alt={'tools':[tool],'input_rules':[{'path':'/'+k,'op':'eq','right':v,'atol':1e-9,'rtol':1e-9} for k,v in args.items()], 'output_rules':checks or [{'path':'','op':'type','value':'object'}]}
        node={'id':n,'alternatives':[alt]}
        if deps:node['depends_on']=deps
        if branch:node['branch']=branch
        self.nodes.append(node);self.plan.append((n,tool,args,branch));return n
    def branch(self,name,n,path,operator,threshold):
        self.branches.append({'id':name,'when':{'left':N(n,path),'op':operator,'value':threshold}});return name
    def out(self,key,target,typ='number',evidence=None,branch=None,atol=1e-6):
        if key not in self.properties:self.properties[key]={'type':typ}
        out={'id':key+('_'+branch if branch else ''),'left':{'source':'answer','path':'/'+key},'op':'eq','right':target,'evidence_nodes':evidence or sorted(set(refs(target))),'atol':atol,'rtol':1e-6}
        if branch:out['branch']=branch
        self.outcomes.append(out)
    def selection(self,key,ids,values,maximize=False,evidence=None):
        rows=E('paired_rows',V(ids),E('array',*values));self.properties[key]={'type':'array','items':{'type':'string'},'uniqueItems':True}
        self.outcomes.append({'id':key,'left':{'source':'answer','path':'/'+key},'op':'set_equal','right':E('argmax' if maximize else 'argmin',rows,id_path='/0',value_path='/1',tie_atol=1e-9),'evidence_nodes':evidence or sorted(set(refs(values)))})
    def finish(self,shared,parallel,stop='Every specified branch is scientifically required.',repair='None required.'):
        ev={'schema_version':'workflow.v1','nodes':self.nodes,'outcomes':self.outcomes}
        if self.branches:ev['branches']=self.branches
        validate_workflow(ev)
        filename=self.id+'-study.json'; schema={'type':'object','properties':self.properties,'required':list(self.properties),'additionalProperties':False}
        task={'id':self.id,'domain':'MachineLearning','question':self.title+'. '+self.question+' Return the named answer fields as JSON. Numeric values must agree within absolute 1e-6 plus relative 1e-6; winner ties use absolute 1e-9. Array order follows the supplied data order unless explicitly stated otherwise.','inputs':self.inputs,'files':['asset://'+filename],'answer_schema':schema,'question_language':'en','Parameter':json.dumps(self.inputs,separators=(',',':')),'unit_annotations':[{'description':self.units}]}
        PREFLIGHT_PLANS[self.id]=self.plan
        return {'task':task,'evaluation':ev,'design':{'scientific_goal':self.question,'parallel_branches':parallel,'shared_preprocessing':shared,'early_stop_logic':stop,'repair_opportunity':repair,'case_study':self.strong,'source_notes':'Pinned finite fixtures; native local catalog contracts. Targets are expressions over actual tool observations, never hand-authored numerical golds. Seeded algorithms use stated seeds; no inference beyond the stated population/design.'},'assets':{filename:self.inputs}}

def build():
    PREFLIGHT_PLANS.clear(); result=[]
    # 39: group-level generalization; a single shared split prevents repeat leakage.
    x=[[0,0],[0.2,0.1],[1,0.2],[1.1,0.4],[2,0.8],[2.2,0.9],[3,1.1],[3.1,1.4],[4,1.5],[4.2,1.8],[5,2.1],[5.2,2.2]]
    s=Study(39,'Generalization to unseen calibration devices','Each device contributes two repeated readings. Split whole devices, using test_fraction=1/3 and seed=17. Fit unpenalized-intercept ridge regressions with penalties 0.05, 1 and 20 to the training rows only. For each penalty report heldout predictions (pred_a, pred_b, pred_c), RMSE (rmse_a, rmse_b, rmse_c), and choose all minimum-RMSE penalties as selected IDs a,b,c. Also report train_indices and test_indices. Do not evaluate on a random reading-level split.',{'features':x,'targets':[0.1,0.4,1.0,1.2,2.1,2.3,2.7,2.9,4.2,4.5,4.8,5.0],'groups':['d1','d1','d2','d2','d3','d3','d4','d4','d5','d5','d6','d6']},True)
    s.add('split','GroupTrainTestSplit',{'features':I('/features'),'targets':I('/targets'),'groups':I('/groups'),'test_fraction':V(1/3),'seed':V(17)})
    for k in ['train_indices','test_indices']:s.out(k,N('split','/'+k),'array')
    for label,alpha in zip('abc',[0.05,1.,20.]):
        fit=s.add('fit_'+label,'FitRidgeRegression',{'training_features':N('split','/training_features'),'targets':N('split','/training_targets'),'alpha':V(alpha)})
        pred=s.add('predict_'+label,'PredictLinearModel',{'model':N(fit,'/model'),'features':N('split','/test_features')})
        metric=s.add('metric_'+label,'RegressionMetrics',{'truth':N('split','/test_targets'),'predicted':N(pred,'/predictions')})
        s.out('pred_'+label,N(pred,'/predictions'),'array');s.out('rmse_'+label,N(metric,'/rmse'))
    s.selection('selected',list('abc'),[N('metric_'+k,'/rmse') for k in 'abc'])
    result.append(s.finish('One whole-device split reused by every training, prediction and scoring branch.','Three independent ridge/prediction/metric branches join at heldout model choice.'))
    # 40: a single graph generator supports spectral and transient analyses.
    s=Study(40,'Diffusion smoothing on a weighted sensor graph','Use the unnormalized degree-minus-adjacency Laplacian. Report its ascending spectrum (spectrum). For times 0.2, 0.8 and 1.6 report states state_a,state_b,state_c = exp(-t L) times initial. Report squared Euclidean discrepancy error_a,error_b,error_c against target; choose all minimum-discrepancy times as selected IDs a,b,c. Edge weights are inverse-time; times use the corresponding time unit.',{'adjacency':[[0,1,0,0],[1,0,2,0],[0,2,0,1],[0,0,1,0]],'initial':[1,0,0,0],'target':[0.45,0.3,0.18,0.07]},True)
    s.add('lap','GraphLaplacian',{'adjacency':I('/adjacency')});s.add('spectrum','SymmetricEigenDecomposition',{'values':N('lap','/laplacian')});s.out('spectrum',N('spectrum','/eigenvalues'),'array')
    for label,t in zip('abc',[.2,.8,1.6]):
        scaled=E('numeric_rows',*[E('array',*[E('multiply',V(-t),N('lap',f'/laplacian/{i}/{j}')) for j in range(4)]) for i in range(4)])
        exp=s.add('exp_'+label,'MatrixExponential',{'values':scaled});prop=s.add('state_'+label,'MatrixMultiply',{'left':N(exp,'/exponential'),'right':I('/initial')})
        err=s.add('error_'+label,'RegressionMetrics',{'truth':I('/target'),'predicted':N(prop,'/product')});s.out('state_'+label,N(prop,'/product'),'array');s.out('error_'+label,E('multiply',V(4),N(err,'/mse')))
    s.selection('selected',list('abc'),[N('error_'+k,'/mse') for k in 'abc'])
    result.append(s.finish('One graph Laplacian feeds spectral analysis and every transient time.','Spectrum and three exponential/propagation/discrepancy branches.'))
    # 41: a rejected covariance is an observed eigenvalue decision, not a tool error.
    s=Study(41,'Admissibility of covariance proposals','For each symmetric proposal report ascending eigenvalues eig_a,eig_b,eig_c. A covariance is admissible iff its smallest eigenvalue is strictly greater than 1e-8. Report accepted_a,accepted_b,accepted_c. For admissible proposals report inverse_a etc. and an independent direct linear-system solution_a etc. to covariance times solution = rhs. For rejected proposals report null for both fields and stop that solve branch. Never replace a failed computation with evidence of a negative eigenvalue.',{'proposals':[[[2,.3],[.3,1]],[[1,2],[2,1]],[[1,.99],[.99,1]]],'rhs':[1,-.5]},True)
    for i,label in enumerate('abc'):
        eig=s.add('eig_'+label,'SymmetricEigenDecomposition',{'values':I(f'/proposals/{i}')});yes=s.branch('positive_'+label,eig,'/eigenvalues/0','gt',1e-8);no=s.branch('nonpositive_'+label,eig,'/eigenvalues/0','le',1e-8)
        s.out('eig_'+label,N(eig,'/eigenvalues'),'array')
        for branch,flag in [(yes,True),(no,False)]:s.out('accepted_'+label,V(flag),'boolean',[eig],branch)
        inverse=s.add('inverse_'+label,'MatrixInverse',{'values':I(f'/proposals/{i}')},parents=[eig],branch=yes)
        solve=s.add('solve_'+label,'SolveLinearSystem',{'matrix_a':I(f'/proposals/{i}'),'vector_b':I('/rhs')},parents=[eig],branch=yes)
        for key,node,path in [('inverse',inverse,'/inverse'),('solution',solve,'/solution')]:
            s.out(key+'_'+label,N(node,path),['array','null'],[eig,node],yes);s.out(key+'_'+label,V(None),['array','null'],[eig],no)
    result.append(s.finish('Per-proposal eigenspectrum controls both inverse and direct-solve eligibility.','Three independent spectra; two accepted numerical methods per admissible matrix.','An observed smallest eigenvalue <=1e-8 terminates both downstream branches with explicit nulls.'))
    # 42: repeated-measures comparison, a joint family and effect uncertainty.
    s=Study(42,'Paired optimizer comparison across benchmark instances','The same six independent benchmark instances are paired across optimizers. For each optimizer compare its loss against baseline with an exact two-sided within-pair sign randomization test, using mean optimizer minus baseline as contrast. Report p_a,p_b,p_c and effect_a,effect_b,effect_c. Adjust the three p-values jointly by Benjamini-Hochberg and report q_values in optimizer order. Also report 95% percentile bootstrap effect intervals ci_a,ci_b,ci_c using independent benchmark-instance differences, 400 resamples, seed 23.',{'baseline':[10,11,9,12,10,13],'optimizers':[[8,9,8,10,9,10],[9,12,8,11,10,12],[10,11,10,12,11,13]]})
    for i,label in enumerate('abc'):
        test=s.add('test_'+label,'PairedRandomizationTest',{'sample_a':I(f'/optimizers/{i}'),'sample_b':I('/baseline'),'alternative':V('two-sided')})
        differences=E('array',*[E('subtract',I(f'/optimizers/{i}/{j}'),I(f'/baseline/{j}')) for j in range(6)])
        boot=s.add('boot_'+label,'BootstrapMeanInterval',{'values':differences,'confidence':V(.95),'resamples':V(400),'seed':V(23)})
        s.out('p_'+label,N(test,'/p_value'));s.out('effect_'+label,N(test,'/observed_mean_difference'));s.out('ci_'+label,E('array',N(boot,'/lower'),N(boot,'/upper')),'array')
    s.add('adjust','AdjustPValues',{'p_values':E('array',*[N('test_'+k,'/p_value') for k in 'abc']),'method':V('bh')});s.out('q_values',N('adjust','/adjusted_p_values'),'array')
    result.append(s.finish('Each test and effect interval use the same scientific within-instance contrast.','Three exact tests and three bootstrap branches; all tests join at one multiplicity family.'))
    # 43: one fitted probabilistic model, multiple decision policies.
    s=Study(43,'Cost-sensitive deployment thresholds','Fit population feature standardization on training data only, then fit binary logistic regression on standardized training data with regularization C=1, at most 300 iterations; apply the same fitted standardization when evaluating heldout rows. Class 1 is positive. Report positive_probabilities and Brier score brier. Apply probability >= threshold for thresholds 0.25,0.5,0.75, returning labels labels_a,labels_b,labels_c. False positives cost 2 and false negatives cost 7. Report cost_a,cost_b,cost_c as total heldout costs and select all minimum-cost threshold IDs a,b,c.',{'training_features':[[-3],[-2],[-1],[-.5],[.5],[1],[2],[3]],'training_targets':[0,0,0,1,0,1,1,1],'heldout_features':[[-1.5],[-.25],[.25],[1.5],[2.5]],'heldout_targets':[0,1,0,1,1]})
    s.add('fit','FitLogisticRegression',{'training_features':I('/training_features'),'targets':I('/training_targets'),'regularization_c':V(1.),'max_iterations':V(300)})
    s.add('probability','PredictLogisticModel',{'model':N('fit','/model'),'features':I('/heldout_features')});prob=E('column',N('probability','/probabilities'),V(1));s.out('positive_probabilities',prob,'array')
    s.add('calibration','ProbabilityCalibrationSummary',{'truth':I('/heldout_targets'),'probabilities':prob,'positive_label':V(1),'bins':V(5)});s.out('brier',N('calibration','/brier_score'))
    for label,t in zip('abc',[.25,.5,.75]):
        th=s.add('threshold_'+label,'ThresholdClassProbabilities',{'probabilities':prob,'threshold':V(t),'positive_label':V(1),'negative_label':V(0)})
        cost=s.add('cost_'+label,'DecisionCostSummary',{'truth':I('/heldout_targets'),'predicted':N(th,'/predicted'),'positive_label':V(1),'false_positive_cost':V(2),'false_negative_cost':V(7)})
        s.out('labels_'+label,N(th,'/predicted'),'array');s.out('cost_'+label,N(cost,'/total_cost'))
    s.selection('selected',list('abc'),[N('cost_'+k,'/total_cost') for k in 'abc'])
    result.append(s.finish('A single training-only model and heldout probability vector are reused.','Calibration and three threshold/cost branches join at policy selection.'))
    # 44: a derivative and integration audit with source-bound gradients.
    s=Study(44,'Discrete derivative consistency in three numerical sensors','For each sensor on the supplied strictly increasing time grid, estimate dy/dt with numpy.gradient edge_order=1. Report gradient_a,gradient_b,gradient_c and the trapezoidal integral of each estimated gradient as recovered_change_a etc. Report closure_error_a etc. = recovered_change minus the last-minus-first source response. In parallel evaluate the cubic Hermite interpolant at query_times using the estimated knot gradients, returning midpoint_a etc. Select every minimum-absolute-closure-error sensor ID a,b,c as selected. These are discretization diagnostics, not error bars.',{'times':[0,.4,1.1,2,3],'sensors':[[0,.16,1.21,4,9],[0,.5,.9,1.3,1.8],[1,1.1,1.4,1.5,1.7]],'query_times':[.2,.75,1.55,2.5]},units='Time is seconds; source responses are volts; gradients are V/s and recovered changes/closure errors/interpolated responses are V.')
    closure=[]
    for i,label in enumerate('abc'):
        grad=s.add('gradient_'+label,'FiniteDifferenceGradient',{'x':I('/times'),'y':I(f'/sensors/{i}')});integral=s.add('integral_'+label,'NumericalTrapezoidIntegration',{'x':I('/times'),'y':N(grad,'/gradient')})
        interp=s.add('hermite_'+label,'CubicHermiteInterpolate',{'x':I('/times'),'y':I(f'/sensors/{i}'),'derivatives':N(grad,'/gradient'),'query_x':I('/query_times')})
        err=E('subtract',N(integral,'/integral'),E('subtract',I(f'/sensors/{i}/4'),I(f'/sensors/{i}/0')));closure.append(E('abs',err))
        s.out('gradient_'+label,N(grad,'/gradient'),'array');s.out('recovered_change_'+label,N(integral,'/integral'));s.out('closure_error_'+label,err);s.out('midpoint_'+label,N(interp,'/values'),'array')
    s.selection('selected',list('abc'),closure)
    result.append(s.finish('One source gradient per sensor is reused for integration and Hermite interpolation.','Three gradient branches, each forking into independent integral and interpolation audits.'))
    # 45: source constraints, unique optimal points, and explicit products.
    s=Study(45,'Resource allocation under three capacity scenarios','Allocate nonnegative continuous amounts of two compute jobs. Maximize revenue per scenario with the supplied per-job revenues, the same resource coefficient matrix, and scenario capacities; each job amount is at most 20. For scenarios a,b,c report allocation_a etc., revenue_a etc., and resource_use_a etc. Also report objective_check_a etc. from the revenue row times the allocation. Solve each scenario separately; choose all largest-revenue scenario IDs as selected. Constraints are linear and these are continuous quantities.',{'resource_matrix':[[1,2],[3,1]],'revenues':[5,4],'capacities':[[12,15],[10,18],[14,12]]},True,units='Job quantities and resource capacities use declared abstract units; revenue is credits; products preserve these units.')
    for i,label in enumerate('abc'):
        lp=s.add('optimum_'+label,'SolveLinearProgram',{'objective':I('/revenues'),'bounds':V([[0,20],[0,20]]),'inequality_matrix':I('/resource_matrix'),'inequality_rhs':I(f'/capacities/{i}'),'direction':V('max')},checks=[{'path':'/status','op':'eq','value':'optimal'},{'path':'/diagnostics/scaled_duality_gap','op':'le','value':1e-7},{'path':'/diagnostics/scaled_stationarity_violation','op':'le','value':1e-7}])
        use=s.add('resource_'+label,'MatrixMultiply',{'left':I('/resource_matrix'),'right':N(lp,'/solution')});obj=s.add('objective_'+label,'MatrixMultiply',{'left':E('numeric_rows',I('/revenues')),'right':N(lp,'/solution')})
        s.out('allocation_'+label,N(lp,'/solution'),'array');s.out('revenue_'+label,N(lp,'/objective_value'));s.out('resource_use_'+label,N(use,'/product'),'array');s.out('objective_check_'+label,N(obj,'/product/0'))
    s.selection('selected',list('abc'),[N('optimum_'+k,'/objective_value') for k in 'abc'],True)
    result.append(s.finish('Shared resource matrix/revenue convention is reused in all scenarios and both independent validation products.','Three LP solves each fork to resource and objective products; validated objectives join at scenario comparison.'))
    # 46: geometry scale sensitivity rather than another supervised fit.
    s=Study(46,'Scale sensitivity of unsupervised clustering','Compare raw features with population-standardized features fitted on this same exploratory dataset. For each representation fit two-cluster Euclidean KMeans with ten initializations and seed 31. Report raw_labels, standardized_labels, raw_silhouette and standardized_silhouette with Euclidean silhouette. Report adjusted_rand between the two partitions, and the full Euclidean matrices raw_distances and standardized_distances. Cluster labels are arbitrary integer IDs; any renaming of the same seeded partition is acceptable.',{'features':[[0,0],[.1,80],[.2,160],[3,5],[3.1,85],[3.2,165]]},units='First raw coordinate is a dimensionless score, second is milliseconds; standardized coordinates and their distances are dimensionless. Raw Euclidean results explicitly use the supplied numerical scales.')
    s.add('standardize','StandardizeNumericFeatures',{'training_features':I('/features'),'features':I('/features')})
    for label,data in [('raw',I('/features')),('standardized',N('standardize','/features'))]:
        fit=s.add('cluster_'+label,'KMeansClustering',{'features':data,'clusters':V(2),'seed':V(31)})
        quality=s.add('quality_'+label,'ClusteringQualityMetrics',{'features':data,'labels':N(fit,'/labels')});dist=s.add('distance_'+label,'PairwiseNumericDistances',{'values':data,'metric':V('euclidean')})
        s.out(label+'_labels',N(fit,'/labels'),'array');s.outcomes[-1]['left']=E('partition_profile',{'source':'answer','path':'/'+label+'_labels'},V(False));s.outcomes[-1]['right']=E('partition_profile',N(fit,'/labels'),V(False));s.out(label+'_silhouette',N(quality,'/silhouette'));s.out(label+'_distances',N(dist,'/distances'),'array')
    s.add('agreement','AdjustedRandAgreement',{'labels_a':N('cluster_raw','/labels'),'labels_b':N('cluster_standardized','/labels')});s.out('adjusted_rand',N('agreement','/adjusted_rand_index'))
    result.append(s.finish('A single standardized dataset feeds standardized clustering, quality and geometry.','Raw and standardized geometry/cluster/quality branches join in label-invariant agreement.'))
    # 47: heldout compression; training-only transformations shared by dimensions.
    s=Study(47,'Compression fidelity on future feature vectors','Fit coordinate-wise population standardization to training features only and apply it separately to training and heldout rows. For PCA dimensions 1,2,3, fit the PCA basis exclusively to standardized training rows. Report heldout reconstruction MSE mse_a,mse_b,mse_c and training explained-variance ratios variance_a,variance_b,variance_c. Independently project heldout features into the first two training principal components and report the squared Euclidean distance matrix projected_distances. PCA sign choices must not affect this matrix.',{'training_features':[[0,0,0],[1,1.2,.5],[2,1.8,1.4],[3,3.2,1.1],[4,3.7,2.4],[5,5.1,2.1]],'heldout_features':[[.5,.7,.4],[2.5,2.7,1.9],[4.5,4.1,2.8]]})
    s.add('scale_training','StandardizeNumericFeatures',{'training_features':I('/training_features'),'features':I('/training_features')});s.add('scale_heldout','StandardizeNumericFeatures',{'training_features':I('/training_features'),'features':I('/heldout_features')})
    for label,k in zip('abc',[1,2,3]):
        p=s.add('pca_'+label,'PCAReconstructionError',{'training_features':N('scale_training','/features'),'features':N('scale_heldout','/features'),'n_components':V(k)})
        s.out('mse_'+label,N(p,'/reconstruction_mse'));s.out('variance_'+label,N(p,'/explained_variance_ratio'),'array')
    s.add('projection','PrincipalComponentProjection',{'training_features':N('scale_training','/features'),'features':N('scale_heldout','/features'),'n_components':V(2)})
    s.add('distances','PairwiseNumericDistances',{'values':N('projection','/features'),'metric':V('euclidean')})
    squared=E('numeric_rows',*[E('array',*[E('multiply',N('distances',f'/distances/{i}/{j}'),N('distances',f'/distances/{i}/{j}')) for j in range(3)]) for i in range(3)])
    s.out('projected_distances',squared,'array')
    result.append(s.finish('Training-only scaling is reused by all dimensionality choices and the projection branch.','Three heldout reconstruction branches plus an independent two-component projected geometry branch.'))
    # 48: finite-population audit planning, contrasted with replacement sampling.
    s=Study(48,'Coverage planning for a finite model-audit inventory','There are 40 auditable model configurations; feature counts are numbers of configurations carrying each failure flag and flags may overlap. For uniform sampling without replacement at sample sizes 4,8,12, report finite_absence_a,b,c (per-flag zero-hit probabilities) and expected_flags_a,b,c (expected number of detected flags). For the rare flag with count 3, independently report zero-hit probabilities replacement_absence_a,b,c under independent with-replacement draws, and gaps gap_a,b,c = replacement minus finite rare-flag absence. No independence across different failure flags is assumed.',{'population_size':40,'flag_counts':[3,8,17,0],'sample_sizes':[4,8,12]})
    s.add('coverage','FinitePopulationCoverage',{'population_size':I('/population_size'),'feature_success_counts':I('/flag_counts'),'sample_sizes':I('/sample_sizes')})
    # One complete distribution and one summary branch per design size.
    for i,label in enumerate('abc'):
        b=s.add('replacement_'+label,'BinomialProbabilityTable',{'n':I(f'/sample_sizes/{i}'),'p':E('divide',I('/flag_counts/0'),I('/population_size'))})
        summary=s.add('mass_summary_'+label,'DescribeNumericData',{'values':N(b,'/pmf')})
        s.out('finite_absence_'+label,N('coverage',f'/analyses/{i}/feature_absence_probabilities'),'array');s.out('expected_flags_'+label,N('coverage',f'/analyses/{i}/expected_detected_features'))
        s.out('replacement_absence_'+label,N(b,'/pmf/0'));s.out('gap_'+label,E('subtract',N(b,'/pmf/0'),N('coverage',f'/analyses/{i}/feature_absence_probabilities/0')))
        s.out('pmf_max_'+label,N(summary,'/maximum'))
    s.question+=' Also report pmf_max_a,b,c: the maximum probability mass in each complete rare-flag with-replacement count distribution.'
    result.append(s.finish('One finite-population analysis shares population/count conventions across every sampling size.','Three independent replacement count distributions and distribution-mass summaries are compared to the finite-population branches.'))
    # 49: finite known families with heldout, not training, model comparison.
    s=Study(49,'Response-curve family comparison for a learning saturation study','Fit three candidate families to training points: a exponential approach y=amplitude*(1-exp(-rate*x)), b power law y=amplitude*x**exponent, c logistic y=amplitude/(1+exp(-rate*(x-midpoint))). Use linear loss, at most 2000 function evaluations, initial parameters and bounds as supplied. Evaluate each fitted family at heldout_x and report predictions_a,b,c, heldout_rmse_a,b,c, and convergence_a,b,c. Select every minimum-heldout-RMSE family ID. Do not select by training residuals.',{'training_x':[1,2,3,4,5,6,7],'training_y':[.65,1.1,1.48,1.68,1.86,1.98,2.08],'heldout_x':[1.5,3.5,6.5],'heldout_y':[.91,1.57,2.04],'initial':[[2.3,.3],[.7,.6],[2.4,.7,2]],'lower':[[.1,.01],[.01,.01],[.1,.01,-3]],'upper':[[5,3],[5,3],[5,5,10]]},units='x is a dimensionless training-budget coordinate and response is a dimensionless score; curve coefficients follow the explicit formulas.')
    for i,(label,family) in enumerate(zip('abc',['exponential_approach','power_law','logistic'])):
        fit=s.add('fit_'+label,'FitParametricCurve',{'x':I('/training_x'),'y':I('/training_y'),'model_type':V(family),'initial_parameters':I(f'/initial/{i}'),'lower_bounds':I(f'/lower/{i}'),'upper_bounds':I(f'/upper/{i}'),'loss':V('linear'),'max_evaluations':V(2000)})
        pred=s.add('evaluate_'+label,'EvaluateParametricCurve',{'model':N(fit,'/model'),'x':I('/heldout_x')});metric=s.add('metric_'+label,'RegressionMetrics',{'truth':I('/heldout_y'),'predicted':N(pred,'/predictions')})
        s.out('predictions_'+label,N(pred,'/predictions'),'array');s.out('heldout_rmse_'+label,N(metric,'/rmse'));s.out('convergence_'+label,N(fit,'/optimizer/converged'),'boolean')
    s.selection('selected',list('abc'),[N('metric_'+k,'/rmse') for k in 'abc'])
    result.append(s.finish('Shared training and heldout observations have fixed roles across every family.','Three fit/evaluate/heldout-score branches join at family selection.'))
    # 50: multiple roots are data, not a single arbitrary inverse prediction.
    s=Study(50,'Inverse calibration and branch ambiguity','Fit degree-2 ordinary least-squares response curves for sensors a,b,c against the supplied dose grid. Report descending-power coefficients coefficients_a,b,c. For each sensor solve fitted_response(dose)=target_response and report all numerical complex roots roots_a,b,c as {real,imag} records sorted by (real,imag), retaining both roots rather than selecting one. Report turning_a,b,c as the real part of the unique derivative root. Report root_residuals_a,b,c as original-equation absolute residuals returned by the numerical root calculation. The physical dose support is the closed interval [-2,2]; additionally report supported_roots_a,b,c containing every root with |imag|<=1e-8 and real part inside support. Root multiplicity or support filtering must not be silently conflated with unique identifiability.',{'dose':[-2,-1,0,1,2],'responses':[[4.1,1.05,0,1.02,4.08],[6.05,2.02,0,.04,2.01],[-1.95,.01,1.02,1.04,.03]],'target_response':[1,1,-1]},True,units='Dose is a dimensionless calibration coordinate; sensor responses are dimensionless. Polynomial coefficients and derivative turning points use those declared coordinates.')
    for i,label in enumerate('abc'):
        fit=s.add('calibration_'+label,'PolynomialLeastSquaresFit',{'x':I('/dose'),'y':I(f'/responses/{i}'),'degree':V(2)})
        inverse_coeff=E('array',N(fit,'/coefficients/0'),N(fit,'/coefficients/1'),E('subtract',N(fit,'/coefficients/2'),I(f'/target_response/{i}')))
        roots=s.add('inverse_'+label,'PolynomialRoots',{'coefficients':inverse_coeff})
        derivative=s.add('turning_'+label,'PolynomialRoots',{'coefficients':E('array',E('multiply',V(2),N(fit,'/coefficients/0')),N(fit,'/coefficients/1'))})
        s.out('coefficients_'+label,N(fit,'/coefficients'),'array');s.out('roots_'+label,N(roots,'/roots'),'array');s.out('turning_'+label,N(derivative,'/roots/0/real'));s.out('root_residuals_'+label,N(roots,'/absolute_residuals'),'array')
        # Source spectra are real for these finite fixtures; support membership
        # of the upper root is an observed conditional outcome, not a golden ID.
        inside=s.branch('upper_supported_'+label,roots,'/roots/1/real','le',2)
        outside=s.branch('upper_excluded_'+label,roots,'/roots/1/real','gt',2)
        reals=E('array',N(roots,'/roots/0/real'),N(roots,'/roots/1/real'))
        s.out('supported_roots_'+label,reals,'array',[roots],inside)
        s.outcomes[-1]['scientific_domains']=[{'path':f'/supported_roots_{label}/{j}','minimum':-2,'maximum':2} for j in range(2)]
        s.out('supported_roots_'+label,E('array',N(roots,'/roots/0/real')),'array',[roots],outside)
        s.outcomes[-1]['scientific_domains']=[{'path':f'/supported_roots_{label}/0','minimum':-2,'maximum':2}]
    result.append(s.finish('Each fitted polynomial is shared by inverse-target and derivative-root branches.','Three fitted calibrations each fork to all inverse roots and turning-point roots; observed roots determine ambiguity.',repair='Numerically complex roots must be retained as such; support selection is explicit rather than guessing an inverse branch.'))
    return result


def preflight(task_ids=None, max_workers=4):
    """Check real native contracts and every outcome, without saving any answers.

    This is an authoring consistency check, not a solver reference actor. It
    returns only task IDs and counts; observations and numerical answers stay
    local to each check and are discarded on return.
    """
    from concurrent.futures import ThreadPoolExecutor
    from jsonschema import Draft202012Validator
    from pathlib import Path
    from tools import execute
    from evaluation.workflow import operand, predicate, score_workflow
    workflow_schema=json.loads(Path('evaluation/workflow/schema.json').read_text())
    specs=build(); plans=dict(PREFLIGHT_PLANS)
    if task_ids is not None: specs=[s for s in specs if s['task']['id'] in task_ids]
    def check(spec):
        task=spec['task']; evaluation=spec['evaluation']
        Draft202012Validator(workflow_schema).validate(evaluation)
        Draft202012Validator.check_schema(task['answer_schema'])
        context={'inputs':task['inputs'],'answer':{},'nodes':{}}
        branches={b['id']:b['when'] for b in evaluation.get('branches',[])}
        calls=[]
        for name,tool,argexpr,branch in plans[task['id']]:
            if branch and not predicate(branches[branch],context):continue
            arguments={k:operand(v,context) for k,v in argexpr.items()}
            result=execute(tool,arguments)
            assert result['status']=='success',(task['id'],name,result)
            call={'observation_id':name,'tool':tool,'arguments':arguments,'output':result['output'],'status':result['status']}
            context['nodes'][name]=call;calls.append(call)
        for outcome in evaluation['outcomes']:
            if outcome.get('branch') and not predicate(branches[outcome['branch']],context):continue
            left=outcome['left'];target=outcome['right']
            if left.get('operation')=='partition_profile':
                left=left['args'][0];target=target['args'][0]
            context['answer'][left['path'][1:]]=operand(target,context)
        for outcome in evaluation['outcomes']:
            if outcome.get('branch') and not predicate(branches[outcome['branch']],context):continue
            assert predicate(outcome,context),(task['id'],outcome['id'])
        Draft202012Validator(task['answer_schema']).validate(context['answer'])
        scored=score_workflow({**task,'evaluation':evaluation},{'completed':True,'final_answer':context['answer'],'calls':calls})
        assert scored['planning_pass'] and scored['answer_pass'],(task['id'],scored)
        return {'id':task['id'],'active_scientific_calls':len(calls),'contracts':True,'outcomes':True,'workflow':True}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(check,specs))
