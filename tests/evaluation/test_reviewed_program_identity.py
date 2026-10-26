import unittest
from evaluation.workflow.program_identity import reviewed_program_identity
from evaluation.workflow.values import MissingEvidence
from evaluation.workflow.expressions import operand

class ReviewedProgramIdentityTests(unittest.TestCase):
    def test_format_changes_preserve_the_whole_reviewed_program(self):
        original='x = [1, 2, 3]\ny = sum(x) / len(x)\nprint(y)'
        formatted='# Independently formatted\nx=[1,2,3]\n\ny=(sum(x)/len(x)) # mean\nprint( y )\n'
        self.assertEqual(reviewed_program_identity(original),reviewed_program_identity(formatted))
        expr={'operation':'reviewed_program_identity','args':[{'value':formatted}]}
        self.assertEqual(operand(expr,{}),reviewed_program_identity(original))

    def test_values_names_scientific_operators_and_order_are_preserved(self):
        original='a = [1, 2]\nb = sum(a) / len(a)\nprint(b)'
        for changed in ['a = [1, 3]\nb = sum(a) / len(a)\nprint(b)',
                        'a = [1, 2]\nb = sum(a) * len(a)\nprint(b)',
                        'print(1.5)',
                        'a = [True, 2]\nb = sum(a) / len(a)\nprint(b)',
                        'a = [1, 2]\nprint(b)\nb = sum(a) / len(a)',
                        original+'\nprint(999)',
                        original.replace('a =','different =',1)]:
            self.assertNotEqual(reviewed_program_identity(original),reviewed_program_identity(changed))

    def test_no_execution_and_explicit_lists(self):
        source="raise RuntimeError('must never execute')"
        self.assertEqual(reviewed_program_identity([source]),[reviewed_program_identity(source)])
        self.assertNotEqual(reviewed_program_identity('x=1'),reviewed_program_identity('x=1.0'))
        self.assertNotEqual(reviewed_program_identity('"original doc"\nx=1'),reviewed_program_identity('"changed doc"\nx=1'))

    def test_malformed_and_excessive_inputs_fail_closed(self):
        for value in [None,False,{},[],['x=1',2],'x =', 'x=1\n'*20000, '+' .join(['x']*4000)]:
            with self.assertRaises(MissingEvidence):reviewed_program_identity(value)

if __name__=='__main__':unittest.main()
