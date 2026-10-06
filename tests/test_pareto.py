import unittest

from src.config_loader import load_model


class ParetoContractTests(unittest.TestCase):
    def test_primary_vector_and_directions(self):
        pareto = load_model()["pareto"]
        self.assertEqual(
            pareto["primary_criteria"],
            [
                {"field": "E_life", "direction": "maximize"},
                {"field": "A_life", "direction": "maximize"},
                {"field": "WLC", "direction": "minimize"},
                {"field": "B_dist", "direction": "minimize"},
                {"field": "M", "direction": "maximize"},
                {"field": "I", "direction": "maximize"},
                {"field": "C", "direction": "maximize"},
            ],
        )

    def test_no_weights_or_normalization(self):
        pareto = load_model()["pareto"]
        self.assertIsNone(pareto["weights"])
        self.assertIsNone(pareto["normalization"])

    def test_combined_circularity_is_a_structural_test(self):
        test = load_model()["pareto"]["criterion_structure_test"]
        self.assertEqual(test["replace"], ["M", "I", "C"])
        self.assertEqual(test["with"], {"field": "CIRC", "direction": "maximize"})


if __name__ == "__main__":
    unittest.main()
