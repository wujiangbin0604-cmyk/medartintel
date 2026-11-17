import numpy as np
import torch

from src.evaluation.final_explanations import integrated_gradients


def test_integrated_gradients_recovers_linear_logit_difference():
    class LinearSignal(torch.nn.Module):
        def forward(self, wave):
            value = (wave * torch.tensor([[[1., -2., .5]]])).sum((1, 2))
            return torch.stack((value + 3, -value), dim=1)
    attrs, timing, quality = integrated_gradients(LinearSignal(), [2, 1, 4], [1, 2, 3, 4], 0, steps=8)
    np.testing.assert_allclose(attrs, [2, -2, 2], atol=1e-6)
    np.testing.assert_array_equal(timing, np.zeros(4))
    assert quality["completeness_absolute_error"] < 1e-6
