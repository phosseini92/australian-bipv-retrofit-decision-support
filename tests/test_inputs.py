from __future__ import annotations

import csv
import hashlib
import itertools
import json
import unittest
from pathlib import Path

from src.config_loader import load_variants
from src.input_loader import INPUT_DIR, INPUT_FILES, iter_input_rows


ROOT = Path(__file__).resolve().parents[1]


class InputSnapshotTests(unittest.TestCase):
    def test_locked_source_hashes(self):
        manifest = json.loads((INPUT_DIR / "source_manifest.yaml").read_text(encoding="utf-8"))
        actual = {item["filename"]: item["sha256"] for item in manifest["sources"]}
        self.assertEqual(
            actual,
            {
                "APSRC_Research_Design_v2.0_LOCK.docx": "d7e505c5844708f27d65b69db26c5c9e078a4a1d839005bb9e1d0fef025a6811",
                "APSRC_Input_Table_v1.0_F_LOCK.xlsx": "9982df28318a674dba9168d9d51b96fbf1e8633d5e7ae6d33e99c5f39b1a3d25",
                "APSRC_Analysis_Specification_v1.0_LOCK.docx": "3891f04ea97b49bb546a78e3537fb64fd3cfbe12360f4c8c6506e049d8028e67",
            },
        )

    def test_exported_row_counts_match_locked_workbook(self):
        expected = {
            "building.csv": 18,
            "pv_electrical.csv": 42,
            "lifecycle.csv": 23,
            "costs.csv": 29,
            "pscf_evidence.csv": 26,
            "sensitivity.csv": 28,
        }
        for filename, count in expected.items():
            self.assertEqual(len(list(iter_input_rows(filename))), count, filename)

    def test_export_hashes_match_manifest(self):
        manifest = json.loads((INPUT_DIR / "source_manifest.yaml").read_text(encoding="utf-8"))
        for item in manifest["exports"]:
            value = hashlib.sha256((INPUT_DIR / item["file"]).read_bytes()).hexdigest()
            self.assertEqual(value, item["sha256"], item["file"])

    def test_every_formula_has_a_cached_machine_readable_value(self):
        for filename in INPUT_FILES:
            for row in iter_input_rows(filename):
                for value, formula in (
                    (row.central, row.central_formula),
                    (row.low, row.low_formula),
                    (row.high, row.high_formula),
                ):
                    if formula:
                        self.assertIsNotNone(value, f"{filename}:{row.source_row}")
                        self.assertTrue(formula.startswith("="))

    def test_source_register_ids_are_unique(self):
        with (INPUT_DIR / "sources.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        ids = [row["source_id"] for row in rows]
        self.assertEqual(len(ids), 38)
        self.assertEqual(len(ids), len(set(ids)))


class VariantMatrixTests(unittest.TestCase):
    def test_exact_v01_to_v08_order(self):
        variants = load_variants()["variants"]
        self.assertEqual([item["id"] for item in variants], [f"V{i:02d}" for i in range(1, 9)])
        self.assertEqual(
            [item["short_code"] for item in variants],
            ["D-L-A", "D-L-C", "D-R-A", "D-R-C", "V-L-A", "V-L-C", "V-R-A", "V-R-C"],
        )

    def test_matrix_is_complete_factorial_without_duplicates(self):
        config = load_variants()
        actual = {
            (item["mounting"], item["connection"], item["replacement_scope"])
            for item in config["variants"]
        }
        expected = set(itertools.product(*config["factors"].values()))
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 8)


if __name__ == "__main__":
    unittest.main()
