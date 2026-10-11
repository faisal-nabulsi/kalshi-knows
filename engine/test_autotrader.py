"""Unit tests: .venv/bin/python -m pytest engine/test_autotrader.py -q  (or run directly)."""
import base64
import os
import tempfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from engine import autotrader as at
from engine import kalshi_auth as ka


def test_signing_roundtrip_and_message_format():
    pk = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ts = 1700000000123
    # query string must be stripped from the signed path
    s = ka.signature(pk, ts, "post", "/trade-api/v2/portfolio/orders?x=1")
    assert ka.verify(pk.public_key(), s, ts, "POST", "/trade-api/v2/portfolio/orders")
    assert not ka.verify(pk.public_key(), s, ts, "GET", "/trade-api/v2/portfolio/orders")
    assert not ka.verify(pk.public_key(), s, ts + 1, "POST", "/trade-api/v2/portfolio/orders")
    assert len(base64.b64decode(s)) == 256
    h = ka.auth_headers(pk, "kid", "GET", "/trade-api/v2/portfolio/balance", ts)
    assert h["KALSHI-ACCESS-TIMESTAMP"] == str(ts) and h["KALSHI-ACCESS-KEY"] == "kid"


def test_demo_only_guard():
    assert ka.DEMO_BASE == "https://external-api.demo.kalshi.co/trade-api/v2"
    ka.guard_demo_only({"PATH": "/bin", "KALSHI_DEMO_KEY_ID": "abc"})
    for bad in ({"KALSHI_API_BASE": "https://api.elections.kalshi.com/trade-api/v2"},
                {"KALSHI_BASE_URL": "https://trading-api.kalshi.com"},
                {"KALSHI_ENV": "prod"}, {"KALSHI_X": "https://api.kalshi.com/v2"}):
        with pytest.raises(ka.NotDemoError):
            ka.guard_demo_only(bad)
    for url in ("https://api.elections.kalshi.com/trade-api/v2/x", "http://demo-api.kalshi.co/trade-api/v2/x",
                "https://demo-api.kalshi.co.evil.com/trade-api/v2/x", "https://evil.com/demo-api.kalshi.co"):
        with pytest.raises(ka.NotDemoError):
            ka.assert_demo_url(url)
    ka.assert_demo_url(ka.DEMO_BASE + "/portfolio/orders")


def test_build_request_preview_masks_and_targets_demo(monkeypatch):
    monkeypatch.setattr(ka, "have_credentials", lambda: False)
    r = ka.build_request("POST", "/portfolio/orders", {"a": 1}, preview=True)
    assert r["url"].startswith(ka.DEMO_BASE) and r["signed_with"] == "ephemeral-preview-key"
    with pytest.raises(ka.NotDemoError):
        ka.build_request("POST", "/portfolio/orders", {})


BOOK = {"yes": [(0.60, 10), (0.55, 50)], "no": [(0.38, 4), (0.30, 100)]}   # yes asks: 0.62 x4, 0.70 x100


def test_dry_run_fill_walks_book_with_limit_and_fee():
    s = at.simulate_fill(BOOK, "yes", 10, 0.65)
    assert s["filled"] == 4 and s["status"] == "partial" and s["avg_price"] == 0.62
    assert s["fees"] == at.kalshi_fee(4, 0.62)
    s = at.simulate_fill(BOOK, "yes", 10, 0.75)
    assert s["status"] == "filled" and [f["count"] for f in s["fills"]] == [4, 6]
    assert at.simulate_fill(BOOK, "yes", 5, 0.50)["status"] == "resting"
    assert at.simulate_fill(BOOK, "no", 3, 0.45)["fills"][0]["price"] == 0.40   # 1 - best yes bid


def test_fee_formula():
    assert at.kalshi_fee(1, 0.5) == 0.02 and at.kalshi_fee(100, 0.5) == 1.75 and at.kalshi_fee(0, .5) == 0


@pytest.fixture
def sandbox(monkeypatch, tmp_path):
    monkeypatch.setattr(at, "DIR", tmp_path)
    monkeypatch.setattr(at, "ORDERS", [])
    monkeypatch.setattr(at, "_cid_seen", set())
    monkeypatch.setattr(at, "SETTINGS", dict(at.DEFAULT_SETTINGS))
    monkeypatch.setattr(at, "CACHE", {"pnl": None, "pnl_ts": 0})
    monkeypatch.setattr(at, "fetch_book", lambda t, demo=False: BOOK)
    monkeypatch.setattr(ka, "have_credentials", lambda: False)
    return tmp_path


RULE = {"id": "t1", "name": "t", "limits": {"max_contracts_per_order": 3, "max_usd_per_day": 4.0, "cooldown_s": 0}}


def test_limits_and_idempotency(sandbox):
    o = at.submit_order(RULE, {}, "KX-A", "yes", 10, "k1", max_slippage=0.10)
    assert o["count"] == 3 and o["mode"] == "dry_run" and o["limit_price"] == 0.72   # clamped to 3 contracts
    assert at.submit_order(RULE, {}, "KX-A", "yes", 10, "k1") is None                  # same trigger: no duplicate
    o2 = at.submit_order(RULE, {}, "KX-A", "yes", 10, "k2", max_slippage=0.10)         # 3*.72*2 = 4.32 > $4 cap
    assert o2["status"] == "skipped" and "cap" in o2["reason"]


def test_kill_switch_and_loss_cap(sandbox):
    at.SETTINGS["kill"] = True
    assert at.submit_order(RULE, {}, "KX-A", "yes", 1, "k1")["reason"] == "kill switch on"
    at.SETTINGS["kill"] = False
    at.CACHE["pnl"] = {"today": -26.0, "exposure": 0}
    assert "loss cap" in at.submit_order(RULE, {}, "KX-A", "yes", 1, "k2")["reason"]


def test_alert_matching():
    a = {"id": "a_1", "team": "SF", "named": True, "headline": "49ers touchdown (90% sure)",
         "inferred": [{"type": "TD", "team": "SF", "prob": 0.9}]}
    t = {"team": "SF", "play_type": "TD", "min_confidence": 0.85, "named_only": True}
    assert at.alert_matches(t, a)
    assert not at.alert_matches(dict(t, min_confidence=0.95), a)
    assert not at.alert_matches(dict(t, team="SEA"), a)
    assert not at.alert_matches(t, dict(a, named=False))
    assert not at.alert_matches(dict(t, play_type="FG"), a)


def test_mover_math_and_politics_filter():
    at.HIST["T"] = at.deque([(100.0, 0.30), (130.0, 0.40), (160.0, 0.50)])
    m = at.move_over("T", 60, 160.0)
    assert m["p_then"] == 0.40 or m["p_then"] == 0.30   # oldest sample within 2x window
    assert abs(m["move"]) >= 0.1
    assert at.is_politics({"ticker": "KXPRESIDENT-28", "title": "x"})
    assert at.is_politics({"ticker": "KXFOO", "title": "Will the Senate pass it?"})
    assert not at.is_politics({"ticker": "KXNFLGAME-1", "title": "Houston vs Tennessee"})


def test_starter_rules_validate():
    for r in at.STARTER_RULES:
        at.validate_rule(r)
