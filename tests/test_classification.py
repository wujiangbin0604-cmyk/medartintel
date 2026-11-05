import unittest

import numpy as np
import torch

from src.evaluation.metrics import score_predictions
from src.models.classifiers import HeartbeatCNN
from src.training.trainer import class_weights_from_training


class ClassificationTests(unittest.TestCase):
    def test_inverse_frequency_weights_derive_from_training_labels(self):
        weights = class_weights_from_training(np.array([0, 0, 0, 1]), 2)
        np.testing.assert_allclose(weights, np.array([2/3, 2.0], dtype=np.float32))

    def test_missing_training_class_is_rejected(self):
        with self.assertRaises(ValueError):
            class_weights_from_training(np.array([0, 0, 0]), 2)

    def test_cnn_emits_one_logit_vector_per_beat(self):
        model = HeartbeatCNN(num_classes=4)
        output = model(torch.zeros((5, 1, 253), dtype=torch.float32))
        self.assertEqual(tuple(output.shape), (5, 4))
        self.assertTrue(torch.isfinite(output).all())

    def test_metrics_keep_absent_classes_in_macro_and_confusion(self):
        result = score_predictions(np.array([0, 0, 1]), np.array([0, 0, 0]), ["N", "V", "F"])
        self.assertEqual(result["per_class"]["F"]["support"], 0)
        self.assertEqual(result["per_class"]["V"]["recall"], 0)
        self.assertEqual(np.asarray(result["confusion_matrix"]).shape, (3, 3))


if __name__ == "__main__":
    unittest.main()
