from pathlib import Path

import pytest

from web.backend.ecg_service import InferenceService


ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def service():
    instance = InferenceService(ROOT)
    import web.backend.app as app_module

    app_module.service = instance
    return instance


def eligible_sample(service, record_id="200", labels=("N", "V"), task="nsvf"):
    context = service.store.signal_context(record_id)
    frame = context.record.annotations
    candidates = frame[(frame["annotation_kind"] == "mapped_beat") & frame["aami_group"].isin(labels)]
    for row in candidates.itertuples(index=False):
        try:
            service.store.beat(record_id, int(row.sample), task)
            return int(row.sample)
        except ValueError:
            continue
    raise AssertionError(f"No eligible {labels} beat found in record {record_id}")


@pytest.fixture(scope="session")
def record_200_sample(service):
    return eligible_sample(service)


@pytest.fixture(scope="session")
def record_200_s_sample(service):
    return eligible_sample(service, labels=("S",), task="nsvf")
