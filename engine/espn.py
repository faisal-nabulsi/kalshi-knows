"""ESPN public NFL JSON: scoreboard + per-game plays (with wallclock)."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime

import httpx

SB_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
SUM_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"
log = logging.getLogger("espn")

_client = httpx.Client(timeout=httpx.Timeout(6.0, connect=4.0),
                       headers={"User-Agent": "kalshi-knows-hackathon/0.1"})


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_ms(s: str | None) -> int | None:
    if not s:
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return None


def clock_seconds(clock: str | None) -> int:
    try:
        m, s = (clock or "0:00").split(":")
        return int(m) * 60 + int(float(s))
    except ValueError:
        return 0


def game_seconds_remaining(period: int, clock: str | None) -> int:
    if not period:
        return 3600
    secs = clock_seconds(clock)
    if period >= 5:
        return secs
    return max(0, (4 - period) * 900 + secs)


def yardline_100(possession_text: str | None, posteam: str | None) -> int | None:
    """'CHI 44' with posteam GB -> 44 yards to the opponent end zone; 'GB 44' -> 56."""
    if not possession_text:
        return None
    m = re.match(r"\s*([A-Z]+)?\s*(\d+)", possession_text)
    if not m:
        return None
    side, n = m.group(1), int(m.group(2))
    if n == 50 or not side:
        return 50
    if posteam and side == posteam:
        return 100 - n
    return n


def fetch_scoreboard(dates: str | None = None) -> list[dict]:
    params = {"dates": dates} if dates else None
    d = _client.get(SB_URL, params=params).json()
    out = []
    for e in d.get("events") or []:
        c = e["competitions"][0]
        teams = {t["homeAway"]: t for t in c["competitors"]}
        if "home" not in teams or "away" not in teams:
            continue
        h, a = teams["home"], teams["away"]
        id2abbr = {h["team"]["id"]: h["team"]["abbreviation"], a["team"]["id"]: a["team"]["abbreviation"]}
        st = e.get("status") or {}
        sit = c.get("situation") or {}
        pos = id2abbr.get(str(sit.get("possession"))) if sit.get("possession") else None
        period = st.get("period") or 0
        clock = st.get("displayClock") or "0:00"
        g = {
            "game_id": str(e["id"]),
            "date_ms": iso_ms(e.get("date")),
            "short_name": f'{a["team"]["abbreviation"]} @ {h["team"]["abbreviation"]}',
            "home": h["team"]["abbreviation"], "away": a["team"]["abbreviation"],
            "home_id": str(h["team"]["id"]), "away_id": str(a["team"]["id"]),
            "home_name": h["team"].get("shortDisplayName") or h["team"].get("name"),
            "away_name": a["team"].get("shortDisplayName") or a["team"].get("name"),
            "home_score": int(h.get("score") or 0), "away_score": int(a.get("score") or 0),
            "period": period, "clock": clock,
            "status": (st.get("type") or {}).get("state", "pre"),
            "status_detail": (st.get("type") or {}).get("shortDetail"),
            "possession": pos,
            "situation": sit.get("downDistanceText") or "",
            "down": sit.get("down") if (sit.get("down") or -1) > 0 else None,
            "ydstogo": sit.get("distance"),
            "yardline_100": yardline_100(sit.get("possessionText"), pos),
            "possession_text": sit.get("possessionText"),
            "red_zone": bool(sit.get("isRedZone")),
            "game_seconds_remaining": game_seconds_remaining(period, clock),
            "last_play_text": ((sit.get("lastPlay") or {}).get("text") or "")[:240],
        }
        out.append(g)
    return out


# ---------------------------------------------------------------- plays

TD_RE = re.compile(r"touchdown", re.I)


def classify(p: dict) -> str:
    t = (p.get("type_text") or "").lower()
    text = (p.get("text") or "").lower()
    if p.get("scoring"):
        if "safety" in t or ("safety" in text and "touchdown" not in text):
            return "SAFETY"
        if "field goal" in t or "field goal is good" in text:
            return "FG"
        if "touchdown" in t or "touchdown" in text:
            return "TD"
        if "extra point" in t or "two-point" in t or "2pt" in t:
            return "OTHER"
    if p.get("is_turnover") or "interception" in t or "fumble recovery (opponent)" in t \
            or "fumble return" in t or "blocked" in t:
        return "TURNOVER"
    if "safety" in t:
        return "SAFETY"
    if (p.get("yards") or 0) >= 20 and not p.get("penalty") and ("punt" not in t and "kickoff" not in t):
        return "BIG_PLAY"
    return "OTHER"


def fetch_plays(event_id: str, home_id: str, away_id: str, home: str, away: str) -> list[dict]:
    d = _client.get(SUM_URL, params={"event": event_id}).json()
    drives = d.get("drives") or {}
    raw = []
    for dr in (drives.get("previous") or []):
        raw.extend(dr.get("plays") or [])
    cur = drives.get("current")
    if cur:
        ids = {p.get("id") for p in raw}
        raw.extend(p for p in (cur.get("plays") or []) if p.get("id") not in ids)
    id2abbr = {str(home_id): home, str(away_id): away}
    out = []
    prev_h = prev_a = 0
    for p in raw:
        st, en = p.get("start") or {}, p.get("end") or {}
        off = id2abbr.get(str((st.get("team") or {}).get("id")))
        end_team = id2abbr.get(str((en.get("team") or {}).get("id")))
        hs, as_ = p.get("homeScore", prev_h) or 0, p.get("awayScore", prev_a) or 0
        q = {
            "id": str(p.get("id")),
            "seq": int(p.get("sequenceNumber") or 0),
            "wallclock_ms": iso_ms(p.get("wallclock")),
            "type_text": (p.get("type") or {}).get("text", ""),
            "text": (p.get("text") or "").strip(),
            "scoring": bool(p.get("scoringPlay")),
            "is_turnover": bool(p.get("isTurnover")),
            "penalty": bool(p.get("isPenalty")),
            "yards": p.get("statYardage") or 0,
            "period": (p.get("period") or {}).get("number"),
            "clock": (p.get("clock") or {}).get("displayValue"),
            "offense": off,
            "start_ytez": st.get("yardsToEndzone"),
            "end_ytez": en.get("yardsToEndzone"),
            "start_down": st.get("down"), "start_dist": st.get("distance"),
            "home_score": hs, "away_score": as_,
        }
        q["type"] = classify(q)
        # beneficiary team: whoever's score went up; defense on turnovers; offense otherwise
        if hs > prev_h and as_ <= prev_a:
            team = home
        elif as_ > prev_a and hs <= prev_h:
            team = away
        elif q["type"] == "TURNOVER":
            team = end_team if end_team and end_team != off else (away if off == home else home)
        elif q["type"] == "SAFETY":
            team = away if off == home else home
        else:
            team = off
        q["team"] = team
        prev_h, prev_a = hs, as_
        out.append(q)
    return out
