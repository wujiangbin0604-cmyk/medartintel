import numpy as np
import pytest
from research_extensions.uncertainty.src.evaluate import uncertainty, policy, selective_metrics


def test_score_and_entropy():
    p=np.array([[1.,0.,0.,0.],[.25,.25,.25,.25]])
    np.testing.assert_allclose(uncertainty(p,"max_score"),[0,.75])
    np.testing.assert_allclose(uncertainty(p,"entropy"),[0,np.log(4)],atol=1e-10)


def test_threshold_calibration_only():
    cal=np.array([[.9,.1],[.6,.4],[.8,.2]])
    before=policy(cal,"max_score")
    uncertainty(np.array([[.5,.5],[1.,0.]]),"max_score")
    assert policy(cal,"max_score")==before


def test_denominators_and_no_accepted_rows():
    p=np.array([[.9,.1],[.7,.3],[.2,.8],[.6,.4]])
    y=np.array([0,1,1,1]);g=np.array(["a","a","b","b"])
    m=selective_metrics(y,p,g,np.array([True,False,True,False]),["N","V"])
    assert m["coverage"]==.5 and m["accepted_error_rate"]==0 and m["rejected_error_rate"]==1
    assert m["per_class"]["V"]["recall_retained_denominator"]==1
    assert m["per_class"]["V"]["recall_all_denominator"]==1/3
    empty=selective_metrics(y,p,g,np.zeros(4,bool),["N","V"])
    assert empty["accepted_error_rate"] is None and empty["coverage"]==0


def test_invalid_score_rows():
    with pytest.raises(ValueError):
        uncertainty([[.1,.2]],"entropy")
