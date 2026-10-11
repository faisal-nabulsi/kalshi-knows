"""Kalshi Knows live engine: FastAPI + pollers + jump detector + alerts + push.

Run:  .venv/bin/python -m engine.live                      (live, port 8000)
      .venv/bin/python -m engine.live --replay docs/data/replay.json --speed 10
      .venv/bin/python -m engine.live --replay engine/logs/20261011 --game 401872992 --speed 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from engine import espn, infer, kalshi, push, tiers

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "engine"
LOG_ROOT = ENGINE_DIR / "logs"
STATIC = ENGINE_DIR / "static"
(STATIC / "audio").mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("live")
for noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------- config

def _threshold() -> tuple[float, str]:
    if os.environ.get("JUMP_THRESHOLD"):
        return float(os.environ["JUMP_THRESHOLD"]), "env"
    p = ROOT / "results" / "detector_sweep.json"
    if p.exists():
        try:
            d = json.loads(p.read_text())
            for k in ("recommended_threshold", "recommended", "best_threshold", "threshold"):
                v = d.get(k)
                if isinstance(v, dict):
                    v = v.get("threshold")
                if isinstance(v, (int, float)) and 0.02 <= v <= 0.4:
                    return float(v), "results/detector_sweep.json"
        except Exception as e:
            log.warning("detector_sweep.json unreadable: %s", e)
    return 0.07, "default"


THRESH, THRESH_SRC = _threshold()
WINDOW_MS = int(float(os.environ.get("JUMP_WINDOW_S", 20)) * 1000)
COOLDOWN_MS = int(float(os.environ.get("JUMP_COOLDOWN_S", 60)) * 1000)
HOLD_MS = int(float(os.environ.get("JUMP_HOLD_S", 3)) * 1000)
HISTORY_MS = 20 * 60 * 1000
POLL_S = float(os.environ.get("KALSHI_POLL_S", 1.75))
CONFIRM_MS = 150_000
CONFIRM_TYPES = {"TD", "FG", "TURNOVER", "SAFETY", "BIG_PLAY"}

CFG = {"mode": "live", "replay": None, "speed": 10.0, "game": None, "loop": False, "push": True, "log": True}


# ---------------------------------------------------------------- jsonl logs

class JsonlLog:
    def __init__(self):
        self.lock = threading.Lock()
        self.files: dict[str, object] = {}
        self.day = None

    def write(self, name: str, rec: dict):
        if not CFG["log"]:
            return
        day = datetime.now().strftime("%Y%m%d")
        with self.lock:
            if day != self.day:
                for f in self.files.values():
                    f.close()
                self.files = {}
                self.day = day
            f = self.files.get(name)
            if f is None:
                d = LOG_ROOT / day
                d.mkdir(parents=True, exist_ok=True)
                f = open(d / f"{name}.jsonl", "a", buffering=1)
                self.files[name] = f
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")


JLOG = JsonlLog()


# ---------------------------------------------------------------- engine core

SNAP_KEYS = ("status", "period", "clock", "home_score", "away_score", "possession", "situation",
             "down", "ydstogo", "yardline_100")


class Engine:
    def __init__(self):
        self.lock = threading.RLock()
        self.games: dict[str, dict] = {}
        self.hist: dict[str, deque] = {}
        self.states: dict[str, deque] = {}
        self.plays: dict[str, dict] = {}
        self.det: dict[str, dict] = {}
        self.alerts: list[dict] = []
        self.alert_by_id: dict[str, dict] = {}
        self.events: deque = deque(maxlen=500)   # (seq, alert) for SSE
        self.seq = 0
        self.guesses: dict[str, dict] = {}
        self.unmatched: list[str] = []
        self.kalshi_ok_ms = None
        self.espn_ok_ms = None
        self.kalshi_err = None
        self.espn_err = None
        self.n_alert = 0
        self.dutchbook: dict | None = None
        self.dutchbook_src = None

    # ---- games / ESPN situations
    def update_game(self, g: dict, ts: int):
        gid = g["game_id"]
        with self.lock:
            cur = self.games.setdefault(gid, {"kalshi_home": None, "kalshi_away": None, "p_home": None})
            changed = any(cur.get(k) != g.get(k) for k in SNAP_KEYS)
            cur.update(g)
            st = self.states.setdefault(gid, deque(maxlen=400))
            if changed or not st:
                snap = {k: g.get(k) for k in SNAP_KEYS + ("game_seconds_remaining",)}
                st.append((ts, snap))
                JLOG.write("espn", {"ts_ms": ts, "game_id": gid, **snap,
                                    "last_play_text": g.get("last_play_text")})

    def state_before(self, gid: str, t: int) -> dict:
        g = self.games.get(gid, {})
        st = self.states.get(gid) or deque()
        snap = None
        for ts, s in st:
            if ts <= t:
                snap = s
            else:
                break
        if snap is None:
            snap = st[0][1] if st else {k: g.get(k) for k in SNAP_KEYS}
        pos = snap.get("possession")
        home, away = g.get("home"), g.get("away")
        hs, as_ = snap.get("home_score") or 0, snap.get("away_score") or 0
        if pos == away:
            diff, is_home = as_ - hs, 0
        else:
            diff, is_home = hs - as_, 1 if pos == home else 0
        return {"qtr": snap.get("period") or 1,
                "game_seconds_remaining": snap.get("game_seconds_remaining")
                if snap.get("game_seconds_remaining") is not None
                else espn.game_seconds_remaining(snap.get("period") or 1, snap.get("clock")),
                "score_differential": diff, "posteam_is_home": is_home,
                "down": snap.get("down"), "ydstogo": snap.get("ydstogo"),
                "yardline_100": snap.get("yardline_100"), "posteam": pos,
                "home": home, "away": away}

    # ---- quotes + detector
    def on_quote(self, gid: str, ts: int, p: float, detail: dict | None = None):
        with self.lock:
            g = self.games.get(gid)
            if g is None:
                return
            h = self.hist.setdefault(gid, deque())
            if h and ts <= h[-1][0]:
                return
            h.append((ts, round(p, 4)))
            while h and h[0][0] < ts - HISTORY_MS:
                h.popleft()
            g["p_home"] = round(p, 4)
            if g.get("status") == "in":
                self._detect(gid, ts, p)
        if detail is not None:
            JLOG.write("quotes", {"ts_ms": ts, "game_id": gid, "p_home": round(p, 4), **detail})

    def _detect(self, gid: str, ts: int, p: float):
        d = self.det.setdefault(gid, {"pending": None, "last_fire": -10**15})
        if ts - d["last_fire"] < COOLDOWN_MS:
            d["pending"] = None
            return
        pend = d["pending"]
        if pend:
            move = (p - pend["p_before"]) * pend["sign"]
            if move < THRESH * 0.75:
                d["pending"] = None          # reverted: a one-trade spike
            elif ts - pend["t0"] >= HOLD_MS:
                d["pending"] = None
                d["last_fire"] = ts
                self._fire(gid, ts, pend, p)
                return
            else:
                return
        win = [x for x in self.hist[gid] if x[0] >= ts - WINDOW_MS]
        if len(win) < 2:
            return
        lo = min(win, key=lambda x: x[1])
        hi = max(win, key=lambda x: x[1])
        up, down = p - lo[1], hi[1] - p
        if up >= THRESH and up >= down:
            d["pending"] = {"t0": ts, "p_before": lo[1], "t_before": lo[0], "sign": 1}
        elif down >= THRESH:
            d["pending"] = {"t0": ts, "p_before": hi[1], "t_before": hi[0], "sign": -1}

    def _fire(self, gid: str, ts: int, pend: dict, p_after_home: float):
        g = self.games[gid]
        home_up = pend["sign"] > 0
        team = g["home"] if home_up else g["away"]
        pb_h = pend["p_before"]
        pb, pa = (pb_h, p_after_home) if home_up else (1 - pb_h, 1 - p_after_home)
        state = self.state_before(gid, pend["t_before"] - 1000)
        try:
            inferred = infer.infer_play(state, pb, pa, team)
        except Exception as e:
            log.exception("infer failed: %s", e)
            inferred = [{"type": "OTHER", "team": team, "prob": 1.0}]
        inferred = [dict(r, prob=round(float(r["prob"]), 3)) for r in inferred][:4]
        self.n_alert += 1
        prefix = "r_" if CFG["mode"] == "replay" else "a_"
        aid = f"{prefix}{self.n_alert}"
        top = inferred[0]["prob"] if inferred else 0
        alert = {"id": aid, "ts_ms": ts, "game_id": gid, "team": team,
                 "p_before": round(pb, 4), "p_after": round(pa, 4), "delta": round(pa - pb, 4),
                 "inferred": inferred, "headline": infer.headline(inferred, team),
                 "confirmed": None, **tiers.alert_tier(top),
                 "short_name": g.get("short_name"), "home": g.get("home"), "away": g.get("away"),
                 "p_home_before": round(pb_h, 4), "p_home_after": round(p_after_home, 4),
                 "jump_started_ms": pend["t_before"], "detected_ms": pend["t0"],
                 "state": state, "infer_source": infer.source(),
                 "period": g.get("period"), "clock": g.get("clock"),
                 "updated_ms": ts}
        self.alerts.append(alert)
        self.alert_by_id[aid] = alert
        log.info("ALERT %s %s %s Δ%.3f %s", aid, g.get("short_name"), alert["headline"], alert["delta"], alert["tier_name"])
        self._emit(alert)
        if CFG["push"]:
            body_alert = dict(alert)
            payload = push.alert_payload(body_alert, g)
            payload["body"] = f"{alert['headline']} · Tier: {alert['tier_name']}. Your stream shows it in ~30s."
            try:
                push.send_all(payload)
            except Exception as e:
                log.warning("push failed: %s", e)
        threading.Thread(target=_announce, args=(alert,), daemon=True).start()
        # a play ESPN already posted may confirm immediately
        self.try_confirm(gid, ts)

    def _emit(self, alert: dict):
        self.seq += 1
        self.events.append((self.seq, json.loads(json.dumps(alert))))
        JLOG.write("alerts", alert)

    # ---- plays + confirmation
    def on_plays(self, gid: str, plays: list[dict], seen_ms: int | None, ref_ms: int | None = None):
        new = []
        with self.lock:
            known = self.plays.setdefault(gid, {})
            for p in plays:
                if p["id"] in known:
                    continue
                p = dict(p, seen_ms=seen_ms if seen_ms is not None else p.get("seen_ms"))
                known[p["id"]] = p
                new.append(p)
        for p in new:
            JLOG.write("plays", {"game_id": gid, **p})
        self.try_confirm(gid, ref_ms if ref_ms is not None else (seen_ms or now_ms()))

    def try_confirm(self, gid: str, ref: int):
        with self.lock:
            plays = list((self.plays.get(gid) or {}).values())
            for a in self.alerts:
                if a["game_id"] != gid or a["confirmed"] is not None:
                    continue
                if ref - a["ts_ms"] > CONFIRM_MS + 30_000:
                    continue
                best = None
                for p in plays:
                    if p.get("type") not in CONFIRM_TYPES or p.get("team") != a["team"]:
                        continue
                    seen = p.get("seen_ms")
                    wc = p.get("wallclock_ms") or seen
                    if wc is None:
                        continue
                    if not (a["ts_ms"] - 150_000 <= wc <= a["ts_ms"] + 30_000):
                        continue
                    if seen is not None and seen > a["ts_ms"] + CONFIRM_MS:
                        continue
                    pri = 0 if p["type"] != "BIG_PLAY" else 1
                    key = (pri, abs(wc - (a["ts_ms"] - 10_000)))
                    if best is None or key < best[0]:
                        best = (key, p)
                if best:
                    p = best[1]
                    seen = p.get("seen_ms")
                    a["confirmed"] = {
                        "play_text": p.get("text"), "play_type": p.get("type"),
                        "espn_wallclock_ms": p.get("wallclock_ms"), "espn_seen_ms": seen,
                        "lead_s": round((seen - a["ts_ms"]) / 1000, 1) if seen is not None else None,
                        "market_lag_s": round((a["ts_ms"] - p["wallclock_ms"]) / 1000, 1) if p.get("wallclock_ms") else None,
                        "inferred_correct": bool(a["inferred"]) and a["inferred"][0]["type"] == p.get("type"),
                    }
                    a["updated_ms"] = max(ref, a["ts_ms"])
                    log.info("CONFIRMED %s: %s (lead %.1fs)", a["id"], (p.get("text") or "")[:80],
                             a["confirmed"]["lead_s"] or 0)
                    self._emit(a)

    # ---- API views
    def games_list(self, step: int = 1) -> list[dict]:
        with self.lock:
            out = []
            for gid, g in self.games.items():
                h = list(self.hist.get(gid) or [])
                if step > 1 and h:
                    last = h[-1]
                    h = h[::step]
                    if h[-1] != last:
                        h.append(last)
                out.append({
                    "game_id": gid, "short_name": g.get("short_name"), "home": g.get("home"), "away": g.get("away"),
                    "home_name": g.get("home_name"), "away_name": g.get("away_name"),
                    "home_score": g.get("home_score"), "away_score": g.get("away_score"),
                    "period": g.get("period"), "clock": g.get("clock"), "status": g.get("status"),
                    "status_detail": g.get("status_detail"), "date_ms": g.get("date_ms"),
                    "possession": g.get("possession"), "situation": g.get("situation") or "",
                    "kalshi_home": g.get("kalshi_home"), "kalshi_away": g.get("kalshi_away"),
                    "p_home": g.get("p_home"), "history": [[t, p] for t, p in h],
                })
            order = {"in": 0, "pre": 1, "post": 2}
            out.sort(key=lambda x: (order.get(x["status"], 3), x.get("date_ms") or 0))
            return out

    def tracked_ids(self) -> list[str]:
        with self.lock:
            return [gid for gid, g in self.games.items() if g.get("kalshi_home") and _should_track(g)]


ENGINE = Engine()


def _should_track(g: dict) -> bool:
    st = g.get("status")
    if st == "in":
        return True
    t = g.get("date_ms") or 0
    if st == "pre":
        return t - now_ms() < 45 * 60 * 1000
    if st == "post":
        return now_ms() - t < 5 * 3600 * 1000 and bool(ENGINE.hist.get(g["game_id"]))
    return False


# ---------------------------------------------------------------- announcer (stretch, AWS Polly)

def _announce(alert: dict):
    if os.environ.get("ANNOUNCER", "1") != "1":
        return
    try:
        import boto3
        text = f"Spoiler alert! {alert['short_name']}. {alert['headline'].split(' (')[0]}. Market says {round(100 * alert['inferred'][0]['prob'])} percent."
        polly = boto3.client("polly", region_name="us-east-1")
        r = polly.synthesize_speech(Text=text, OutputFormat="mp3", VoiceId=os.environ.get("POLLY_VOICE", "Matthew"),
                                    Engine="neural")
        fn = f"{alert['id']}.mp3"
        (STATIC / "audio" / fn).write_bytes(r["AudioStream"].read())
        with ENGINE.lock:
            alert["audio_url"] = f"/static/audio/{fn}"
            ENGINE._emit(alert)
    except Exception as e:
        log.info("announcer skipped: %s", e)


# ---------------------------------------------------------------- live pollers

_stop = threading.Event()


def espn_loop():
    while not _stop.is_set():
        t0 = time.time()
        try:
            games = espn.fetch_scoreboard()
            ts = now_ms()
            for g in games:
                ENGINE.update_game(g, ts)
            ENGINE.espn_ok_ms = ts
            ENGINE.espn_err = None
        except Exception as e:
            ENGINE.espn_err = str(e)[:200]
            log.warning("scoreboard failed: %s", e)
        _stop.wait(max(0.5, 5 - (time.time() - t0)))


def summary_loop():
    last: dict[str, float] = {}
    while not _stop.is_set():
        with ENGINE.lock:
            live = [g for g in ENGINE.games.values() if g.get("status") == "in"]
            hot = {a["game_id"] for a in ENGINE.alerts if a["confirmed"] is None and now_ms() - a["ts_ms"] < CONFIRM_MS + 30_000}
        for g in live:
            gid = g["game_id"]
            period = 4 if gid in hot else 8
            if time.time() - last.get(gid, 0) < period:
                continue
            last[gid] = time.time()
            try:
                plays = espn.fetch_plays(gid, g["home_id"], g["away_id"], g["home"], g["away"])
                ENGINE.on_plays(gid, plays, now_ms())
            except Exception as e:
                log.warning("summary %s failed: %s", gid, e)
        _stop.wait(1.0)


def kalshi_loop():
    events: dict = {}
    last_refresh = 0.0
    last_match = 0.0
    while not _stop.is_set():
        t0 = time.time()
        try:
            with ENGINE.lock:
                need = [g for g in ENGINE.games.values() if not g.get("kalshi_home") and g.get("status") != "post"]
            if time.time() - last_refresh > 300 or (need and time.time() - last_refresh > 60):
                events = kalshi.group_events(kalshi.list_nfl_game_markets())
                last_refresh = time.time()
                last_match = 0.0
            if need and events and time.time() - last_match > 10:
                last_match = time.time()
                unmatched = []
                with ENGINE.lock:
                    for g in ENGINE.games.values():
                        if g.get("kalshi_home"):
                            continue
                        h, a = kalshi.match_game(g, events)
                        if h:
                            g["kalshi_home"], g["kalshi_away"] = h, a
                            JLOG.write("games", {"ts_ms": now_ms(), **{k: g.get(k) for k in (
                                "game_id", "short_name", "home", "away", "home_name", "away_name", "date_ms",
                                "kalshi_home", "kalshi_away", "home_id", "away_id")}})
                        elif g.get("status") != "post":
                            unmatched.append(g["short_name"])
                ENGINE.unmatched = unmatched
                if unmatched:
                    log.warning("unmatched ESPN games (no open Kalshi market): %s", unmatched)
            ids = ENGINE.tracked_ids()
            if ids:
                with ENGINE.lock:
                    tick = {gid: (ENGINE.games[gid]["kalshi_home"], ENGINE.games[gid]["kalshi_away"]) for gid in ids}
                q = kalshi.quotes([t for pair in tick.values() for t in pair])
                ts = now_ms()
                for gid, (ht, at) in tick.items():
                    p, detail = kalshi.home_prob(q.get(ht), q.get(at))
                    if p is not None:
                        ENGINE.on_quote(gid, ts, p, detail)
                ENGINE.kalshi_ok_ms = ts
                ENGINE.kalshi_err = None
        except Exception as e:
            ENGINE.kalshi_err = str(e)[:200]
            log.warning("kalshi loop error: %s", e)
        _stop.wait(max(0.2, POLL_S - (time.time() - t0)))


def dutchbook_loop():
    fallback = ROOT / "docs" / "data" / "dutchbook.json"
    while not _stop.is_set():
        res, src = None, None
        try:
            from engine import dutchbook  # written by the dutchbook agent
            res = dutchbook.scan()
            src = "live"
        except Exception as e:
            log.warning("dutchbook scan unavailable: %s", e)
        if not res and fallback.exists():
            try:
                res, src = json.loads(fallback.read_text()), "docs/data/dutchbook.json"
            except ValueError:
                pass
        if res:
            ENGINE.dutchbook = tiers.tag_dutchbook(res)
            ENGINE.dutchbook_src = src
        _stop.wait(60)


def load_today():
    """Restore today's alerts, plays (with original seen_ms) and recent history after a restart."""
    d = LOG_ROOT / datetime.now().strftime("%Y%m%d")
    if not d.exists():
        return
    try:
        if (d / "games.jsonl").exists():
            for ln in open(d / "games.jsonl"):
                r = json.loads(ln)
                g = ENGINE.games.setdefault(r["game_id"], {"p_home": None})
                g.update({k: v for k, v in r.items() if k != "ts_ms"})
        if (d / "plays.jsonl").exists():
            for ln in open(d / "plays.jsonl"):
                r = json.loads(ln)
                ENGINE.plays.setdefault(r["game_id"], {})[r["id"]] = r
        if (d / "alerts.jsonl").exists():
            for ln in open(d / "alerts.jsonl"):
                r = json.loads(ln)
                if r["id"] in ENGINE.alert_by_id:
                    ENGINE.alert_by_id[r["id"]].update(r)
                else:
                    ENGINE.alerts.append(r)
                    ENGINE.alert_by_id[r["id"]] = r
            ENGINE.n_alert = len(ENGINE.alerts)
        if (d / "quotes.jsonl").exists():
            cut = now_ms() - HISTORY_MS
            for ln in open(d / "quotes.jsonl"):
                r = json.loads(ln)
                if r["ts_ms"] >= cut and r["game_id"] in ENGINE.games:
                    ENGINE.hist.setdefault(r["game_id"], deque()).append((r["ts_ms"], r["p_home"]))
        for gid, h in ENGINE.hist.items():
            if h:
                ENGINE.games[gid]["p_home"] = h[-1][1]
        log.info("restored %d alerts, %d games with history from %s", len(ENGINE.alerts), len(ENGINE.hist), d)
    except Exception as e:
        log.warning("restore failed: %s", e)


# ---------------------------------------------------------------- replay

def _load_replay(path: Path, game: str | None):
    """Returns (game_meta, events) where events = sorted [(ts, kind, payload)]."""
    evs = []
    if path.suffix == ".json":
        d = json.loads(path.read_text())
        meta = dict(d["game"])
        meta.setdefault("home_id", "h")
        meta.setdefault("away_id", "a")
        meta["status"] = "in"
        for t, p in d["history"]:
            evs.append((t, "q", p))
        for i, pl in enumerate(d.get("plays") or []):
            seen = pl.get("seen_ms") or pl.get("espn_seen_ms")
            q = {"id": pl.get("id") or f"p{i}", "wallclock_ms": pl.get("wallclock_ms"), "text": pl.get("text"),
                 "type": pl.get("type"), "team": pl.get("team"), "seen_ms": seen}
            evs.append((seen or pl.get("wallclock_ms") or 0, "play", q))
        return meta, sorted(evs, key=lambda e: e[0])
    d = path if path.is_dir() else path.parent
    games = {}
    for ln in open(d / "games.jsonl"):
        r = json.loads(ln)
        games[r["game_id"]] = r
    quotes: dict[str, list] = {}
    for ln in open(d / "quotes.jsonl"):
        r = json.loads(ln)
        quotes.setdefault(r["game_id"], []).append((r["ts_ms"], "q", r["p_home"]))
    if not game:  # pick the game whose price moved the most
        game = max(quotes, key=lambda g: max(p for _, _, p in quotes[g]) - min(p for _, _, p in quotes[g]))
    meta = dict(games[game])
    evs.extend(quotes[game])
    if (d / "espn.jsonl").exists():
        for ln in open(d / "espn.jsonl"):
            r = json.loads(ln)
            if r["game_id"] == game:
                evs.append((r["ts_ms"], "sb", r))
    if (d / "plays.jsonl").exists():
        for ln in open(d / "plays.jsonl"):
            r = json.loads(ln)
            if r["game_id"] == game:
                evs.append((r.get("seen_ms") or r.get("wallclock_ms") or 0, "play", r))
    return meta, sorted(evs, key=lambda e: e[0])


def replay_loop():
    path = Path(CFG["replay"])
    meta, evs = _load_replay(path, CFG["game"])
    speed = max(0.1, float(CFG["speed"]))
    gid = str(meta["game_id"])
    log.info("REPLAY %s: %d events, speed %.1fx", meta.get("short_name"), len(evs), speed)
    while not _stop.is_set():
        t_first = next((e[0] for e in evs if e[1] == "q"), evs[0][0])
        evs_run = [e for e in evs if e[0] >= t_first - 60_000]
        t0 = evs_run[0][0]
        offset = now_ms() - t0          # virtual clock = original game time shifted to now
        start = time.time()
        with ENGINE.lock:
            ENGINE.hist.pop(gid, None)
            ENGINE.states.pop(gid, None)
            ENGINE.plays.pop(gid, None)
            ENGINE.det.pop(gid, None)
            g = {k: meta.get(k) for k in ("game_id", "short_name", "home", "away", "home_name", "away_name",
                                           "home_id", "away_id", "kalshi_home", "kalshi_away")}
            g.update({"game_id": gid, "status": "in", "home_score": meta.get("home_score", 0),
                      "away_score": meta.get("away_score", 0), "period": meta.get("period"),
                      "clock": meta.get("clock"), "possession": meta.get("possession"),
                      "situation": meta.get("situation", ""), "date_ms": now_ms()})
            if not path.suffix == ".json":
                g.update({"home_score": 0, "away_score": 0})
            ENGINE.update_game(g, now_ms())
        for ts, kind, payload in evs_run:
            if _stop.is_set():
                return
            target = start + (ts - t0) / 1000 / speed
            delay = target - time.time()
            if delay > 0:
                time.sleep(delay)
            vts = ts + offset
            if kind == "q":
                ENGINE.on_quote(gid, vts, float(payload))
            elif kind == "sb":
                snap = {k: payload.get(k) for k in SNAP_KEYS + ("game_seconds_remaining",)}
                snap["status"] = "in"
                ENGINE.update_game(dict(ENGINE.games[gid], **snap), vts)
            elif kind == "play":
                p = dict(payload)
                if p.get("wallclock_ms"):
                    p["wallclock_ms"] += offset
                seen = p.get("seen_ms")
                p["seen_ms"] = seen + offset if seen else None
                p["id"] = f"{p.get('id')}"
                ENGINE.on_plays(gid, [p], None, ref_ms=vts)
        log.info("REPLAY finished (%d alerts so far)", len(ENGINE.alerts))
        if not CFG["loop"]:
            with ENGINE.lock:
                ENGINE.games[gid]["status"] = "post"
            return
        time.sleep(3)


# ---------------------------------------------------------------- FastAPI

app = FastAPI(title="Kalshi Knows live engine")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
_started = False


@app.on_event("startup")
def _startup():
    global _started
    if _started:
        return
    _started = True
    push.public_key()
    if CFG["mode"] == "replay":
        CFG["log"] = False
        threading.Thread(target=replay_loop, daemon=True, name="replay").start()
    else:
        load_today()
        for fn in (espn_loop, summary_loop, kalshi_loop):
            threading.Thread(target=fn, daemon=True, name=fn.__name__).start()
    threading.Thread(target=dutchbook_loop, daemon=True, name="dutchbook").start()
    log.info("engine up: mode=%s threshold=%.3f (%s) window=%ds hold=%ds cooldown=%ds",
             CFG["mode"], THRESH, THRESH_SRC, WINDOW_MS // 1000, HOLD_MS // 1000, COOLDOWN_MS // 1000)


@app.on_event("shutdown")
def _shutdown():
    _stop.set()


@app.get("/")
def root():
    return {"ok": True, "service": "kalshi-knows", "see": "/api/health"}


@app.get("/api/health")
def health():
    return {"ok": True, "now_ms": now_ms(), "games_tracked": len(ENGINE.tracked_ids()) if CFG["mode"] == "live"
            else len(ENGINE.games), "mode": CFG["mode"],
            "alerts": len(ENGINE.alerts), "confirmed": sum(1 for a in ENGINE.alerts if a.get("confirmed")),
            "threshold": THRESH, "threshold_source": THRESH_SRC, "window_s": WINDOW_MS / 1000,
            "kalshi_ok_ms": ENGINE.kalshi_ok_ms, "espn_ok_ms": ENGINE.espn_ok_ms,
            "kalshi_err": ENGINE.kalshi_err, "espn_err": ENGINE.espn_err, "unmatched": ENGINE.unmatched,
            "subscribers": len(push.load_subs()), "infer_source": infer.source()}


@app.get("/api/games")
def games(step: int = 1):
    return ENGINE.games_list(step=max(1, step))


@app.get("/api/alerts")
def alerts(since_ms: int = 0, game_id: str | None = None):
    with ENGINE.lock:
        out = [a for a in ENGINE.alerts
               if (a["ts_ms"] > since_ms or a.get("updated_ms", 0) > since_ms)
               and (game_id is None or a["game_id"] == game_id)]
        return json.loads(json.dumps(out))


@app.get("/api/stream")
async def stream(request: Request, full: int = 0):
    step = 1 if full else 4

    async def gen():
        last_seq = ENGINE.seq
        last_games = 0.0
        while True:
            if await request.is_disconnected():
                break
            with ENGINE.lock:
                new = [(s, a) for s, a in ENGINE.events if s > last_seq]
            for s, a in new:
                last_seq = s
                yield {"event": "alert", "data": json.dumps(a)}
            if time.time() - last_games >= 2:
                last_games = time.time()
                yield {"event": "games", "data": json.dumps(ENGINE.games_list(step=step))}
            await asyncio.sleep(0.25)

    return EventSourceResponse(gen(), ping=15, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/push/vapid")
def vapid():
    return {"publicKey": push.public_key()}


@app.post("/api/push/subscribe")
async def subscribe(request: Request):
    try:
        body = await request.json()
        n = push.subscribe(body.get("subscription", body) if isinstance(body, dict) else body)
        return {"ok": True, "subscribers": n}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)[:200]}, status_code=400)


@app.post("/api/push/test")
def push_test():
    payload = {"title": "Kalshi Knows · test", "body": "Push works. Spoilers will land here before your stream shows the play.",
               "url": "./#live", "tag": f"test-{now_ms()}"}
    res = push.send_all(payload, wait=True) or []
    return {"ok": any(r["ok"] for r in res) if res else False, "sent": len(res),
            "delivered": sum(1 for r in res if r["ok"]), "results": res}


@app.post("/api/guess")
async def guess(request: Request):
    b = await request.json()
    aid, nick, g = b.get("alert_id"), (b.get("nickname") or "").strip()[:32], b.get("guess")
    if not aid or not nick or g not in ("TD", "FG", "TURNOVER", "BIG_PLAY", "SAFETY", "OTHER"):
        return JSONResponse({"ok": False, "error": "need alert_id, nickname, guess in TD|FG|TURNOVER|BIG_PLAY"}, 400)
    with ENGINE.lock:
        ENGINE.guesses.setdefault(aid, {})[nick.lower()] = g
    return {"ok": True}


@app.get("/api/guesses")
def guesses(alert_id: str):
    with ENGINE.lock:
        votes = list((ENGINE.guesses.get(alert_id) or {}).values())
    out = {k: votes.count(k) for k in ("TD", "FG", "TURNOVER", "BIG_PLAY")}
    out["n"] = len(votes)
    return out


@app.get("/api/dutchbook")
def dutchbook():
    if ENGINE.dutchbook:
        return ENGINE.dutchbook
    return {"updated_ms": now_ms(), "scanned_events": 0, "scanned_markets": 0, "total_mispricing_usd": 0.0,
            "opportunities": [], "near_misses": [], "by_category": {}}


# ---------------------------------------------------------------- main

def main():
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", help="docs/data/replay.json or an engine/logs/YYYYMMDD dir")
    ap.add_argument("--speed", type=float, default=10.0)
    ap.add_argument("--game", help="game_id to replay from a logs dir (default: biggest mover)")
    ap.add_argument("--loop", action="store_true", help="loop the replay forever")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    a = ap.parse_args()
    if a.replay:
        CFG.update(mode="replay", replay=a.replay, speed=a.speed, game=a.game, loop=a.loop)
    CFG["push"] = not a.no_push
    uvicorn.run(app, host="0.0.0.0", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
