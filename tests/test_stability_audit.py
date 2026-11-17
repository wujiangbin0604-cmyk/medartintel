"""Regression tests for corruption/leakage signals used by the full audit."""
import unittest

import numpy as np

from src.evaluation.stability_audit import (check_partition_overlap,
                                           exact_cross_split_duplicates,
                                           independent_score)


def partitions():
    result = {}
    for index, split in enumerate(("train", "val", "test")):
        result[split] = {"sample_id": np.array([f"{index}:0"]),
                         "record_id": np.array([str(index)]),
                         "subject_id": np.array([f"patient_{index}"]),
                         "annotation_sample": np.array([1000]),
                         "X_filtered": np.full((1, 1, 253), index, dtype=np.float32)}
    return result


class StabilityAuditTests(unittest.TestCase):
    def test_byte_duplicate_signal_crossing_sets_is_detected(self):
        values = partitions()
        self.assertEqual(exact_cross_split_duplicates(values, "X_filtered")["cross_split_matching_window_count"], 0)
        values["test"]["X_filtered"] = values["train"]["X_filtered"].copy()
        result = exact_cross_split_duplicates(values, "X_filtered")
        self.assertEqual(result["cross_split_matching_window_count"], 1)
        self.assertEqual(result["examples"][0]["first_sample_id"], "0:0")

    def test_nearby_windows_same_record_crossing_sets_are_detected(self):
        values = partitions()
        self.assertEqual(check_partition_overlap(values)["same_record_cross_split_overlapping_intervals"], 0)
        values["test"]["record_id"] = values["train"]["record_id"].copy()
        values["test"]["annotation_sample"] = np.array([1252])
        self.assertEqual(check_partition_overlap(values)["same_record_cross_split_overlapping_intervals"], 1)
        values["test"]["annotation_sample"] = np.array([1253])
        self.assertEqual(check_partition_overlap(values)["same_record_cross_split_overlapping_intervals"], 0)

    def test_shared_patient_across_distinct_records_is_not_hidden(self):
        values = partitions()
        values["test"]["subject_id"] = values["train"]["subject_id"].copy()
        result = check_partition_overlap(values)
        self.assertEqual(result["subject_id"]["train:test"], ["patient_0"])
        self.assertEqual(result["record_id"]["train:test"], [])

    def test_metrics_hold_declared_classes_and_confusion_orientation(self):
        result = independent_score(np.array([0, 0, 1]), np.array([0, 1, 1]), ["N", "V", "F"])
        self.assertEqual(result["confusion_matrix"], [[1, 1, 0], [0, 1, 0], [0, 0, 0]])
        self.assertAlmostEqual(result["macro_f1"], 4 / 9)
        self.assertAlmostEqual(result["balanced_accuracy_fixed_labels"], .5)
        with self.assertRaises(ValueError):
            independent_score(np.array([0, 3]), np.array([0, 1]), ["N", "V"])


if __name__ == "__main__":
    unittest.main()
