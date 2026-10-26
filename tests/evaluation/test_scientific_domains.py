import copy
import unittest
from evaluation.workflow.expressions import predicate
from evaluation.workflow.schema import validate_workflow
from evaluation.workflow.contracts import public_answer_contract
from evaluation.workflow import score_workflow
from tests.support.workflows import fixture,run

class ScientificDomainsTests(unittest.TestCase):
    def test_domain_is_strict_even_when_reporting_tolerance_is_wider(self):
        rule={'left':{'source':'answer','path':'/p'},'op':'eq','value':1.,'atol':1e-6,
              'scientific_domains':[{'path':'/p','minimum':0,'maximum':1}]}
        for p,expected in [(1.,True),(1.-1e-12,True),(1.+1e-12,False)]:
            self.assertEqual(predicate(rule,{'answer':{'p':p}}),expected)
        rule['value']=0.
        self.assertTrue(predicate(rule,{'answer':{'p':1e-12}}))
        self.assertFalse(predicate(rule,{'answer':{'p':-1e-12}}))
        self.assertFalse(predicate(rule,{'answer':{'p':None}}))
        self.assertFalse(predicate(rule,{'answer':{'p':False}}))

    def test_domain_preserves_original_outcome_weights_and_evidence(self):
        r=fixture();p=run();o=r['evaluation']['outcomes'][0]
        # Bind a numeric target to the same required original source evidence.
        o.update(left={'source':'answer','path':'/p'},op='eq',right={'value':1.},atol=1e-6)
        p['final_answer']={'p':1.}
        before=score_workflow(r,p)
        o['scientific_domains']=[{'path':'/p','minimum':0,'maximum':1}]
        after=score_workflow(r,p)
        self.assertEqual(len(after['outcomes']),len(before['outcomes']))
        self.assertEqual(after['scientific_credit'],before['scientific_credit'])
        self.assertTrue(after['joint_pass'])
        p['final_answer']['p']=1.+1e-12
        self.assertFalse(score_workflow(r,p)['joint_pass'])
        metadata=public_answer_contract(r)[0]
        self.assertEqual(metadata['scientific_domains'],o['scientific_domains'])
        self.assertNotIn('value',metadata)

    def test_invalid_or_unrelated_domains_are_rejected(self):
        r=fixture();o=r['evaluation']['outcomes'][0]
        for bad in [[],[{'path':'/unrelated','minimum':0}],
                    [{'path':'/selected','minimum':True}],
                    [{'path':'/selected','minimum':2,'maximum':1}],
                    [{'path':'/selected','minimum':0,'extra':1}],
                    [{'path':'/selected'}]]:
            o['scientific_domains']=bad
            with self.assertRaises(ValueError):validate_workflow(r['evaluation'])

if __name__=='__main__':unittest.main()
