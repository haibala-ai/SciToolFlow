doc = {'provenance': {'kind': 'Project-authored controlled statistical example. Values are stipulated observations or population working moments as explicitly stated, not new experimental data.', 'source_scope': 'No outside information is required; every inferential assumption is declared.'}, 'strata': [{'stratum': 'low', 'population_weight': 0.3, 'true_mean': 2.0, 'response_probability': 0.2}, {'stratum': 'high', 'population_weight': 0.7, 'true_mean': 8.0, 'response_probability': 0.8}], 'outcome_models': {'correct': [2.0, 8.0], 'working': [1.0, 6.0]}, 'response_probability_models': {'correct': [0.2, 0.8], 'working': [0.5, 0.5]}, 'model': 'A scalar outcome is selectively recorded. Given stratum, the recording indicator R is independent of the outcome and has the stipulated response_probability, strictly between0and1. The table gives exact population stratum weights and conditional mean outcomes and recording probabilities, not one finite realized sample. Model arrays use the table stratum order. Evaluate the population limit of the augmented inverse-response estimator E[m(X)+R*(Y-m(X))/p(X)]. The complete-population mean is the target. All nuisance predictions are fixed independently of these evaluation moments.', 'goal': 'Audit the robustness claim by comparing all four nuisance-model combinations. A finite-sample guarantee, absence of unmeasured selection or universal correctness when both models are wrong is not assumed.'}
strata = doc["strata"]
w = [s["population_weight"] for s in strata]
mu = [s["true_mean"] for s in strata]
p0 = [s["response_probability"] for s in strata]
m_c = doc["outcome_models"]["correct"]
m_w = doc["outcome_models"]["working"]
p_c = doc["response_probability_models"]["correct"]
p_w = doc["response_probability_models"]["working"]
n = len(strata)
complete = sum(w[i]*mu[i] for i in range(n))
est_cc = sum(w[i]*(m_c[i] + p0[i]*(mu[i]-m_c[i])/p_c[i]) for i in range(n))
est_cw = sum(w[i]*(m_c[i] + p0[i]*(mu[i]-m_c[i])/p_w[i]) for i in range(n))
est_wc = sum(w[i]*(m_w[i] + p0[i]*(mu[i]-m_w[i])/p_c[i]) for i in range(n))
est_ww = sum(w[i]*(m_w[i] + p0[i]*(mu[i]-m_w[i])/p_w[i]) for i in range(n))
bias = est_ww - complete
print("stratum_weights", w)
print("true_conditional_means", mu)
print("true_response_probabilities", p0)
print("complete_population_mean", complete)
print("correct|correct", est_cc)
print("correct|working", est_cw)
print("working|correct", est_wc)
print("working|working", est_ww)
print("both_working_bias", bias)
print("scope", "probability limits under declared conditional recording assumptions; not finite-sample unbiasedness")
