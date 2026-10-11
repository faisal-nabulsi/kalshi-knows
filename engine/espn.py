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
            or "fumble return" in t or "blocked" in t or "on downs" in t or "turnover on downs" in text:
        return "TURNOVER"          # turnover on downs counts as a turnover, like the training labels
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
    # ESPN's own win probability AFTER each play (home perspective); delta vs the previous play that has one.
    wp = {}
    for w in d.get("winprobability") or []:
        try:
            wp[str(w.get("playId"))] = float(w["homeWinPercentage"])
        except (KeyError, TypeError, ValueError):
            continue
    prev_wp = None
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
        w = wp.get(q["id"])
        if w is not None:
            q["wp_home"] = round(w, 4)
            q["wp_delta_home"] = round(w - prev_wp, 4) if prev_wp is not None else None
            prev_wp = w
        prev_h, prev_a = hs, as_
        out.append(q)
    return out


# ---------------------------------------------------------------- swing plays (no TD/FG/turnover/20+ yd play)

def _ord(n) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(n, "")


_NOT_A_SNAP = re.compile(r"end of|end period|end quarter|end game|timeout|two-minute|coin toss|end of half", re.I)


def is_snap(p: dict) -> bool:
    """False for clock/admin rows (timeouts, end of quarter) whose WP change is just carry-over."""
    return not _NOT_A_SNAP.search(p.get("type_text") or "") and not _NOT_A_SNAP.search((p.get("text") or "")[:20])


def swing_kind(p: dict, team: str | None) -> tuple[str, str]:
    """Plain-English (kind, detail) for a play that moved ESPN's win probability in `team`'s favour."""
    t = (p.get("type_text") or "").lower()
    text = (p.get("text") or "").lower()
    down, dist, yds = p.get("start_down"), p.get("start_dist"), p.get("yards") or 0
    late = down in (3, 4)
    if "field goal" in t and ("miss" in t or "no good" in text or "missed" in text):
        m = re.search(r"(\d+)\s*(?:yd|yard)", text)
        return "Missed field goal", f"{m.group(1)}-yard try no good" if m else "kick no good"
    if "punt" in t or "kickoff" in t or "return" in t:
        what = "punt" if "punt" in t or "punts" in text else "kickoff" if "kick" in t or "kicks" in text else "kick"
        if "muff" in text:
            return "Return / special teams", f"muffed {what}"
        if team is not None and p.get("offense") == team:      # the kicking team gained
            return "Return / special teams", f"{what} pins them deep" if what == "punt" else f"{what} coverage"
        return "Return / special teams", f"{what} return"
    if p.get("penalty") or t == "penalty" or "penalty" in t:
        m = re.search(r"penalty on ([a-z]{2,3})-", text)
        return "Penalty swing", f"flag on {m.group(1).upper()}" if m else "flag on the play"
    defense = team is not None and p.get("offense") not in (None, team)
    if defense:
        if "sack" in t or "sacked" in text:
            return "Defensive stop", f"{_ord(down)}-down sack" if late else "sack"
        if late and "incomplet" in text:
            return "Defensive stop", f"{_ord(down)}-down incompletion"
        if late and dist is not None and yds < dist:
            return "Defensive stop", f"{_ord(down)}-down stop" + (f" ({yds:+d} yds)" if yds else "")
        if "incomplet" in text:
            return "Swing play", "incomplete pass"
        return "Swing play", f"stop for {yds:+d} yds" if yds else "defense holds"
    if late and dist is not None and yds >= dist:
        return "Big conversion", f"converts {_ord(down)} & {dist}" + (f" ({yds} yds)" if yds else "")
    if yds:
        return "Swing play", f"{yds:+d} yards"
    return "Swing play", ""
