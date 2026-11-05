"""Local teaching game. Expert answers and authoritative clocks stay in SQLite."""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from .ecg_service import ECGStore

RULES = {"correct": 100, "incorrect": -30, "missed": -20, "combo_step": 10,
         "combo_cap": 4, "time_divisor": 5, "tolerance_seconds": .10, "grace_seconds": 2}
DIFFICULTIES = {
    "beginner": {"name": "新手模式", "seconds": 120, "duration": 10, "candidates": True, "pause": True},
    "standard": {"name": "标准模式", "seconds": 90, "duration": 14, "candidates": False, "pause": False},
    "challenge": {"name": "挑战模式", "seconds": 60, "duration": 24, "candidates": False, "pause": False},
}
INDEX = Path(__file__).parent / "game_data/heartbeat_levels.json"


class Start(BaseModel):
    player_id: str
    difficulty: Literal["beginner", "standard", "challenge"] = "beginner"
    previous_session_id: str | None = None


class Answer(BaseModel):
    session_id: str
    samples: list[StrictInt] = Field(default_factory=list, max_length=128)


class Control(BaseModel):
    session_id: str
    action: Literal["pause", "resume", "abandon", "speed"]
    speed: Literal[0.5, 1, 1.5, 2] = 1


class HunterService:
    def __init__(self, store: ECGStore, database: Path, index: Path = INDEX, clock=time.time):
        self.store, self.index, self.clock = store, index, clock
        self.lock = threading.RLock()
        database.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS hunter_sessions (id TEXT PRIMARY KEY, player TEXT NOT NULL, data TEXT NOT NULL)")
        self.db.execute("CREATE INDEX IF NOT EXISTS hunter_player ON hunter_sessions(player)")
        self.db.commit()
        self._levels = None

    @property
    def levels(self):
        if self._levels is None:
            if not self.index.exists():
                raise HTTPException(503, "关卡索引未生成，请运行 python -m web.backend.build_heartbeat_levels")
            self._levels = json.loads(self.index.read_text(encoding="utf-8"))["levels"]
        return self._levels

    def save(self, session):
        self.db.execute("INSERT OR REPLACE INTO hunter_sessions VALUES (?, ?, ?)",
                        (session["session_id"], session["player_id"], json.dumps(session)))
        self.db.commit()

    def get(self, sid):
        row = self.db.execute("SELECT data FROM hunter_sessions WHERE id=?", (sid,)).fetchone()
        if row is None:
            raise HTTPException(404, "游戏会话不存在，请重新开始挑战")
        return json.loads(row[0])

    def config(self):
        return {"difficulties": DIFFICULTIES, "scoring": RULES, "rounds": 5,
                "level_count": len(self.levels), "source": "MIT-BIH Arrhythmia Database 1.0.0",
                "policy": "仅使用 N/V 可判定片段；S/F/Q、未知心拍整段排除。V 指 AAMI V 组。"}

    def start(self, payload: Start):
        try:
            UUID(payload.player_id)
        except ValueError:
            raise HTTPException(422, "player_id 必须为匿名 UUID")
        with self.lock:
            round_number, used, total = 1, [], 0
            if payload.previous_session_id:
                previous = self.get(payload.previous_session_id)
                if previous["player_id"] != payload.player_id or previous["difficulty"] != payload.difficulty or previous["status"] != "finished":
                    raise HTTPException(409, "上一关尚未完成或不属于本次挑战")
                if previous.get("next_session_id"):
                    return self.public(self.get(previous["next_session_id"]), waveform=True)
                if previous["round"] >= 5:
                    raise HTTPException(409, "五关已完成，请重新挑战")
                round_number = previous["round"] + 1
                used = previous["used_levels"]
                total = previous["total_score"]
            available = [x for x in self.levels if x["difficulty"] == payload.difficulty and x["id"] not in used]
            if not available:
                raise HTTPException(503, "暂无通过校验的关卡")
            level = secrets.choice(available)
            now = self.clock()
            session = {"session_id": secrets.token_urlsafe(32), "player_id": payload.player_id,
                       "difficulty": payload.difficulty, "round": round_number, "level": level,
                       "used_levels": used + [level["id"]], "status": "playing", "started_at": now,
                       "deadline": now + DIFFICULTIES[payload.difficulty]["seconds"], "paused_at": None,
                       "paused_seconds": 0, "samples": [], "total_score": total, "speed": 1,
                       "playback_position": 0, "playback_updated_at": now}
            # Load validated raw physical samples before committing a playable session.
            public = self.public(session, waveform=True)
            self.save(session)
            if payload.previous_session_id:
                previous["next_session_id"] = session["session_id"]
                self.save(previous)
            return public

    def playback(self, session):
        elapsed = 0 if session["paused_at"] else max(0, min(self.clock(), session["deadline"]) - session["playback_updated_at"])
        return min(session["level"]["duration"], session["playback_position"] + elapsed * session["speed"])

    def public(self, session, waveform=False):
        level = session["level"]
        now = self.clock()
        response = {key: session[key] for key in ("session_id", "difficulty", "round", "status", "started_at", "deadline", "samples", "total_score", "speed")}
        response.update({"server_time": now, "remaining_seconds": max(0, session["deadline"] - (session["paused_at"] or now)),
                         "playback_position": self.playback(session), "record_id": level["record_id"],
                         "lead_name": level["lead_name"], "sampling_rate": level["sampling_rate"],
                         "start_sample": level["start_sample"], "end_sample": level["end_sample"],
                         "duration": level["duration"], "historical_signal": True,
                         "candidate_samples": [a["sample"] for a in level["answers"]] if DIFFICULTIES[session["difficulty"]]["candidates"] else []})
        if waveform:
            wave = self.store.window(level["record_id"], level["start_sample"] / level["sampling_rate"], level["duration"], level["lead_name"])
            response["signal"] = [p["amplitude_mv"] for p in wave["points"]]
            if wave["downsampled"]:
                raise HTTPException(503, "关卡原始采样点不完整")
        if session["status"] == "finished":
            response["result"] = session["result"]
        return response

    def validate_samples(self, session, samples):
        level = session["level"]
        if any(s < level["start_sample"] or s >= level["end_sample"] for s in samples):
            raise HTTPException(422, "选择位置超出真实 ECG 片段")
        if session["difficulty"] == "challenge":
            visible = level["start_sample"] + round(self.playback(session) * level["sampling_rate"])
            if any(s > visible for s in samples):
                raise HTTPException(422, "只能选择已回放的历史心拍")
        # Collapse selections inside the same tolerance; reference assignment is still one-to-one.
        unique = []
        tolerance = round(RULES["tolerance_seconds"] * level["sampling_rate"])
        for sample in sorted(set(samples)):
            if not unique or sample - unique[-1] > tolerance:
                unique.append(sample)
        return unique

    def selections(self, payload: Answer):
        with self.lock:
            session = self.get(payload.session_id)
            if session["status"] != "playing" or self.clock() >= session["deadline"]:
                raise HTTPException(409, "当前会话已暂停、结束或超时")
            session["samples"] = self.validate_samples(session, payload.samples)
            self.save(session)
            return {"samples": session["samples"], "server_time": self.clock()}

    def control(self, payload: Control):
        with self.lock:
            session = self.get(payload.session_id)
            if session["status"] in ("finished", "abandoned"):
                raise HTTPException(409, "游戏已结束")
            now = self.clock()
            if now >= session["deadline"] and not session["paused_at"] and payload.action != "abandon":
                raise HTTPException(409, "游戏时间已结束，请结算")
            if payload.action in ("pause", "resume") and not DIFFICULTIES[session["difficulty"]]["pause"]:
                raise HTTPException(409, "限时模式禁止暂停，确保服务器计时公平")
            position = self.playback(session)
            if payload.action == "pause" and session["status"] == "playing":
                session.update(status="paused", paused_at=now)
            elif payload.action == "resume" and session["status"] == "paused":
                delta = now - session["paused_at"]
                session["deadline"] += delta
                session["paused_seconds"] += delta
                session.update(status="playing", paused_at=None)
            elif payload.action == "abandon":
                session.update(status="abandoned", paused_at=None)
            elif payload.action == "speed":
                session["speed"] = payload.speed
            else:
                raise HTTPException(409, "当前状态无法执行该操作")
            session.update(playback_position=position, playback_updated_at=now)
            self.save(session)
            return self.public(session)

    def submit(self, payload: Answer):
        with self.lock:
            session = self.get(payload.session_id)
            if session["status"] == "finished":
                return self.public(session)  # Idempotent retry, never award twice.
            if session["status"] != "playing":
                raise HTTPException(409, "请先恢复游戏或重新开始")
            now = self.clock()
            # After deadline + fixed network grace, only pre-deadline checkpoints count.
            timed_out = now >= session["deadline"]
            samples = session["samples"] if now > session["deadline"] + RULES["grace_seconds"] else self.validate_samples(session, payload.samples)
            level = session["level"]
            tolerance = round(level["sampling_rate"] * RULES["tolerance_seconds"])
            references = level["answers"]
            # Global nearest-first deterministic matching avoids crossing/duplicate assignments.
            edges = sorted((abs(s - a["sample"]), a["sample"], s) for s in samples for a in references if abs(s - a["sample"]) <= tolerance)
            mapping, used = {}, set()
            for distance, ref, sample in edges:
                if sample not in mapping and ref not in used:
                    mapping[sample] = ref
                    used.add(ref)
            lookup = {a["sample"]: a for a in references}
            tp = fp = combo = max_combo = bonus = 0
            events = []
            for sample in samples:
                ref = mapping.get(sample)
                correct = ref is not None and lookup[ref]["label"] == "V"
                if correct:
                    tp += 1
                    combo += 1
                    extra = min(combo - 1, RULES["combo_cap"]) * RULES["combo_step"]
                    bonus += extra
                    delta = RULES["correct"] + extra
                else:
                    fp += 1
                    combo, delta = 0, RULES["incorrect"]
                max_combo = max(max_combo, combo)
                events.append({"sample": sample, "reference_sample": ref, "correct": correct,
                               "delta": delta, "combo": combo, "distance_samples": abs(sample-ref) if ref is not None else None})
            targets = sum(a["label"] == "V" for a in references)
            missed = targets - tp
            remaining = max(0, session["deadline"] - now)
            # Speed bonus only for a perfect round, so empty/random answers cannot farm it.
            time_bonus = int(remaining // RULES["time_divisor"]) if tp == targets and fp == 0 else 0
            score = tp * RULES["correct"] + fp * RULES["incorrect"] + missed * RULES["missed"] + bonus + time_bonus
            result = {"correct": tp, "incorrect": fp, "missed": missed, "precision": tp / (tp + fp) if tp + fp else 0,
                      "recall": tp / targets, "score": score, "combo_bonus": bonus, "time_bonus": time_bonus,
                      "max_combo": max_combo, "events": events, "answers": references,
                      "timed_out": timed_out, "elapsed_seconds": round(min(now, session["deadline"]) - session["started_at"] - session["paused_seconds"], 3),
                      "completed_at": now, "grade": "精准猎手" if tp == targets and fp == 0 else "节律探索者" if tp else "继续练习"}
            session.update(status="finished", samples=samples, result=result, total_score=session["total_score"] + score)
            self.save(session)
            return self.public(session)

    def history(self, player_id):
        with self.lock:
            rows = self.db.execute("SELECT data FROM hunter_sessions WHERE player=? AND json_extract(data, '$.status')='finished' ORDER BY rowid DESC", (player_id,)).fetchall()
        sessions = [json.loads(row[0]) for row in rows]
        finished = [s for s in sessions if s["status"] == "finished"]
        records = [{"session_id": s["session_id"], "difficulty": s["difficulty"], "round": s["round"],
                    **{k:v for k,v in s["result"].items() if k not in ("answers", "events")}} for s in finished]
        return {"records": records[:20], "best": {d: max([s["result"]["score"] for s in finished if s["difficulty"] == d], default=0) for d in DIFFICULTIES}}


def create_router(game: HunterService):
    router = APIRouter(prefix="/api/games/heartbeat-hunter", tags=["心跳猎人"])
    router.add_api_route("/config", game.config, methods=["GET"])
    router.add_api_route("/start", game.start, methods=["POST"])
    router.add_api_route("/selections", game.selections, methods=["POST"])
    router.add_api_route("/control", game.control, methods=["POST"])
    router.add_api_route("/submit", game.submit, methods=["POST"])
    router.add_api_route("/finish", game.submit, methods=["POST"])

    @router.get("/session/{session_id}")
    def session(session_id: str):
        with game.lock:
            return game.public(game.get(session_id), waveform=True)

    @router.get("/leaderboard")
    def leaderboard(player_id: str = Query(min_length=36, max_length=36)):
        return game.history(player_id)

    return router
