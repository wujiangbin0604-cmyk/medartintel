from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from web.backend.heartbeat_hunter import Answer, Control, DIFFICULTIES, HunterService, Start, create_router
from web.backend.build_heartbeat_levels import validate


@pytest.fixture
def game(service, tmp_path):
    now = [1_800_000_000.0]
    instance = HunterService(service.store, tmp_path / "game.sqlite3", clock=lambda: now[0])
    instance.now = now
    yield instance
    instance.db.close()


def begin(game, difficulty="beginner"):
    return game.start(Start(player_id=str(uuid4()), difficulty=difficulty))


def targets(game, sid):
    return [a["sample"] for a in game.get(sid)["level"]["answers"] if a["label"] == "V"]


def test_all_indexed_levels_verified_against_real_files(game):
    assert len(game.levels) >= 15
    for level in game.levels:
        validate(game.store, level)


def test_start_raw_signal_and_no_answer_leak(game):
    public = begin(game)
    level = game.get(public["session_id"])["level"]
    record = game.store.get_record(level["record_id"])
    expected = record.signal[level["start_sample"]:level["end_sample"], record.leads.index(level["lead_name"])]
    np.testing.assert_array_equal(public["signal"], expected)
    assert len(public["signal"]) == public["duration"] * public["sampling_rate"]
    forbidden = {"answers", "label", "symbol", "target_count", "correct_samples", "level", "used_levels", "result"}
    assert forbidden.isdisjoint(public)
    assert all(isinstance(s, int) for s in public["candidate_samples"])
    assert public["session_id"] != level["id"] and len(public["session_id"]) > 32


def test_perfect_correct_combo_and_speed(game):
    s = begin(game)
    selected = targets(game, s["session_id"])
    response = game.submit(Answer(session_id=s["session_id"], samples=selected))
    result = response["result"]
    assert result["correct"] == len(selected) and result["incorrect"] == result["missed"] == 0
    assert result["precision"] == result["recall"] == 1
    assert result["score"] == len(selected)*100 + result["combo_bonus"] + result["time_bonus"]
    assert result["max_combo"] == len(selected)
    assert result["time_bonus"] == 24


def test_wrong_normal_miss_and_unmatched(game):
    s = begin(game)
    level = game.get(s["session_id"])["level"]
    normal = next(a["sample"] for a in level["answers"] if a["label"] == "N")
    result = game.submit(Answer(session_id=s["session_id"], samples=[normal, level["start_sample"]]))["result"]
    assert result["incorrect"] == 2 and result["correct"] == 0
    assert result["missed"] == len(targets(game, s["session_id"]))
    assert result["score"] == -60 - 20*result["missed"] and result["time_bonus"] == 0


def test_duplicates_and_idempotent_submit(game):
    s = begin(game)
    target = targets(game, s["session_id"])[0]
    first = game.submit(Answer(session_id=s["session_id"], samples=[target, target, target+1]))
    assert first["result"]["correct"] == 1
    again = game.submit(Answer(session_id=s["session_id"], samples=[]))
    assert first["result"] == again["result"] and first["total_score"] == again["total_score"]
    assert len(game.history(s_id_player(game,s))["records"]) == 1


def s_id_player(game, s):
    return game.get(s["session_id"])["player_id"]


def test_explicit_tolerance(game):
    for offset, expected in [(36, 1), (37, 0)]:
        s = begin(game)
        target = targets(game, s["session_id"])[0]
        result = game.submit(Answer(session_id=s["session_id"], samples=[target+offset]))["result"]
        assert result["correct"] == expected


def test_one_to_one_nearest_deterministic(game):
    s = begin(game)
    target = targets(game, s["session_id"])[0]
    # Both clicks within tolerance but further than the duplicate-collapse interval.
    result = game.submit(Answer(session_id=s["session_id"], samples=[target-30, target+30]))["result"]
    assert result["correct"] == 1 and result["incorrect"] == 1
    assert result["events"][0]["reference_sample"] == target
    assert result["events"][1]["reference_sample"] is None


def test_deadline_checkpoints_and_late_payload(game):
    s = begin(game)
    target = targets(game, s["session_id"])[0]
    game.selections(Answer(session_id=s["session_id"], samples=[target]))
    game.now[0] += 123
    with pytest.raises(HTTPException) as err:
        game.selections(Answer(session_id=s["session_id"], samples=[]))
    assert err.value.status_code == 409
    response = game.submit(Answer(session_id=s["session_id"], samples=[]))
    assert response["result"]["correct"] == 1 and response["result"]["timed_out"]
    assert response["result"]["time_bonus"] == 0


def test_fixed_network_grace(game):
    s = begin(game)
    target = targets(game, s["session_id"])[0]
    game.now[0] += 121
    response = game.submit(Answer(session_id=s["session_id"], samples=[target]))
    assert response["result"]["correct"] == 1 and response["result"]["timed_out"]


def test_pause_managed_by_server(game):
    s = begin(game)
    game.now[0] += 10
    paused = game.control(Control(session_id=s["session_id"], action="pause"))
    game.now[0] += 300
    assert game.public(game.get(s["session_id"]))["remaining_seconds"] == paused["remaining_seconds"]
    with pytest.raises(HTTPException):
        game.submit(Answer(session_id=s["session_id"], samples=[]))
    resumed = game.control(Control(session_id=s["session_id"], action="resume"))
    assert resumed["remaining_seconds"] == 110
    assert resumed["deadline"] == s["deadline"]+300


@pytest.mark.parametrize("difficulty,seconds", [("beginner",120),("standard",90),("challenge",60)])
def test_difficulty_rules(game, difficulty, seconds):
    s = begin(game, difficulty)
    assert s["deadline"]-s["started_at"] == seconds
    assert bool(s["candidate_samples"]) == (difficulty == "beginner")
    if difficulty != "beginner":
        with pytest.raises(HTTPException):
            game.control(Control(session_id=s["session_id"], action="pause"))


def test_challenge_only_replayed_samples_and_speed(game):
    s = begin(game,"challenge")
    target = targets(game,s["session_id"])[0]
    with pytest.raises(HTTPException):
        game.selections(Answer(session_id=s["session_id"],samples=[target]))
    game.now[0] += 2
    game.control(Control(session_id=s["session_id"],action="speed",speed=2))
    game.now[0] += 3
    assert game.public(game.get(s["session_id"]))["playback_position"] == 8
    game.now[0] += 10
    assert game.selections(Answer(session_id=s["session_id"],samples=[target]))["samples"] == [target]


def test_invalid_session_and_out_of_range(game):
    with pytest.raises(HTTPException) as err:
        game.get("bad-token")
    assert err.value.status_code == 404
    s = begin(game)
    for sample in [-1,s["end_sample"],s["end_sample"]+10000]:
        with pytest.raises(HTTPException) as err:
            game.submit(Answer(session_id=s["session_id"],samples=[sample]))
        assert err.value.status_code == 422


def test_rounds_nonrepeating_next_idempotent_and_history(game):
    player = str(uuid4())
    s = game.start(Start(player_id=player))
    used = []
    for i in range(1,6):
        assert s["round"] == i
        used.append(game.get(s["session_id"])["level"]["id"])
        game.submit(Answer(session_id=s["session_id"],samples=targets(game,s["session_id"])))
        if i < 5:
            payload=Start(player_id=player,previous_session_id=s["session_id"])
            s=game.start(payload)
            assert game.start(payload)["session_id"] == s["session_id"]
    assert len(set(used)) == 5
    with pytest.raises(HTTPException):
        game.start(Start(player_id=player,previous_session_id=s["session_id"]))
    history=game.history(player)
    assert len(history["records"]) == 5 and history["best"]["beginner"] > 0


def test_restart_recovers_persisted_session(game, tmp_path):
    s = begin(game)
    target=targets(game,s["session_id"])[0]
    game.selections(Answer(session_id=s["session_id"],samples=[target]))
    reopened=HunterService(game.store,tmp_path/"game.sqlite3",clock=game.clock)
    try:
        assert reopened.public(reopened.get(s["session_id"]))["samples"] == [target]
    finally:
        reopened.db.close()


def test_api_validation_and_public_schema(game):
    app=FastAPI();app.include_router(create_router(game));client=TestClient(app)
    assert client.post('/api/games/heartbeat-hunter/start',json={"player_id":"bad","difficulty":"beginner"}).status_code==422
    s=begin(game)
    for bad in [1.5,"12",True]:
        assert client.post('/api/games/heartbeat-hunter/submit',json={"session_id":s["session_id"],"samples":[bad]}).status_code==422
    public=client.get('/api/games/heartbeat-hunter/session/'+s["session_id"]).json()
    assert "result" not in public and "answers" not in public
    assert client.get('/api/games/heartbeat-hunter/session/invalid').status_code==404


def test_abandon_expired_and_no_reward(game):
    s=begin(game);game.now[0]+=500
    assert game.control(Control(session_id=s["session_id"],action="abandon"))["status"] == "abandoned"
    with pytest.raises(HTTPException):
        game.submit(Answer(session_id=s["session_id"]))
    assert not game.history(s_id_player(game,s))["records"]
