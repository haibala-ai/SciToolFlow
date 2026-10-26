"""Literal source geometry boundaries, not phylogenetic conclusion fixtures."""

import copy, unittest
from tools.implementations.biology.tree_distances import (
    parse_newick_tree_distances as f,
)


class TreeDistancesTest(unittest.TestCase):
    def test_exact_paths_and_polytomy(self):
        r = f("((A:1,B:2)node:3,C:4,D:5);")
        self.assertEqual(r["tip_ids"], ["A", "B", "C", "D"])
        self.assertEqual(r["root_to_tip_lengths"], [4, 5, 4, 5])
        self.assertEqual(
            r["patristic_distances"],
            [[0, 3, 8, 9], [3, 0, 9, 10], [8, 9, 0, 9], [9, 10, 9, 0]],
        )
        self.assertEqual(r["total_branch_length"], 15)

    def test_reference_root_and_order_do_not_change_pair_paths(self):
        a = f("((A:1,B:2):3,C:4);")
        b = f("(C:4,(B:2,A:1):3):0;")
        for x in a["tip_ids"]:
            for y in a["tip_ids"]:
                self.assertEqual(
                    a["patristic_distances"][a["tip_ids"].index(x)][
                        a["tip_ids"].index(y)
                    ],
                    b["patristic_distances"][b["tip_ids"].index(x)][
                        b["tip_ids"].index(y)
                    ],
                )

    def test_invalid_not_repaired(self):
        for s in [
            "(A:0,B:1);",
            "(A:-1,B:1);",
            "(A:1,B:1):2;",
            "(A:1,A:2);",
            "(A,B:1);",
            "(A:1,B:2);(C:1,D:2);",
            "(A:1:2,B:1);",
            "('A':1,B:2);",
            "(A:1,B:2)[comment];",
            "(A:1e999,B:2);",
            "(A:1e-999,B:2);",
            "(A:1,B:2)",
            "(A:1);",
            "(A:1,);",
            "(A:1,B:2)x y;",
        ]:
            with self.subTest(s=s):
                with self.assertRaises(ValueError):
                    f(s)

    def test_root_stem_zero_is_lexical_not_underflow(self):
        with self.assertRaises(ValueError):
            f("(A:1,B:2):1e-999;")
        for token in ["0e-999", "0.0e999", "+0.000e+999"]:
            result = f("(A:1,B:2):" + token + ";")
            self.assertEqual(result["root_to_tip_lengths"], [1, 2])
            self.assertEqual(result["patristic_distances"][0][1], 3)

    def test_short_private_branch_not_cancelled(self):
        r = f("((A:1e-200,B:2e-200):1e100,C:1);")
        self.assertEqual(r["patristic_distances"][0][1], 3e-200)
        with self.assertRaises(ValueError):
            f("(A:1e308,B:1e308);")


if __name__ == "__main__":
    unittest.main()
