"""Tests: production-key read-only guard, WS signing, feed pricing, two-stage alerts (fake clock).

Run: .venv/bin/python -m pytest engine/test_kalshi_ws.py -q
"""
from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa

from engine import kalshi_auth, kalshi_ws as kws


# ---------------------------------------------------------------- read-only guard

@pytest.mark.parametrize("method,target", [
    ("GET", "/trade-api/v2/markets"),
    ("GET", "/trade-api/v2/portfolio/balance"),
    ("POST", "/trade-api/v2/portfolio/orders"),
    ("DELETE", "/trade-api/v2/portfolio/orders/abc"),
    ("GET", "/portfolio"),
    ("GET", "/trade-api/ws/v2/orders"),
    ("GET", "/trade-api/ws/v2?x=/portfolio"),
    ("GET", "https://api.elections.kalshi.com/trade-api/v2/markets"),
    ("GET", "https://api.elections.kalshi.com/trade-api/ws/v2"),      # https (REST scheme), not wss
    ("GET", "wss://evil.example.com/trade-api/ws/v2"),
    ("POST", "/trade-api/ws/v2"),
    ("POST", "wss://api.elections.kalshi.com/trade-api/ws/v2"),
    ("GET", "/trade-api/ws/v2?cmd=1"),
    ("GET", ""),
])
def test_guard_refuses_everything_but_the_ws_handshake(method, target):
    with pytest.raises(kws.ProdKeyMisuse):
        kws.guard_prod_request(method, target)
    with pytest.raises(kws.ProdKeyMisuse):      # refused before any key is even loaded
        kws.sign_prod(method, target)


@pytest.mark.parametrize("target", ["/trade-api/ws/v2", *kws.WS_URLS])
def test_guard_allows_ws_handshake(target):
    assert kws.guard_prod_request("GET", target) == "/trade-api/ws/v2"


def test_socket_commands_are_market_data_only():
    ok = json.loads(kws.build_cmd(1, "subscribe", {"channels": ["orderbook_delta", "ticker", "trade"],
                                                   "market_tickers": ["KXNFLGAME-26OCT11SFSEA-SEA"]}))
    assert ok["cmd"] == "subscribe" and ok["id"] == 1
    for ch in ("fill", "user_orders", "market_positions", "order_group_updates"):
        with pytest.raises(kws.ProdKeyMisuse):
            kws.build_cmd(2, "subscribe", {"channels": [ch]})
    with pytest.raises(kws.ProdKeyMisuse):
        kws.build_cmd(3, "create_order", {})


# ---------------------------------------------------------------- signing

@pytest.mark.parametrize("make", [lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048),
                                  ed25519.Ed25519PrivateKey.generate])
def test_ws_signature_verifies(make):
    pk = make()
    h = kws.sign_prod("GET", kws.WS_URLS[0], 1791750000000, private_key=pk, key_id="kid")
    assert set(h) == {"KALSHI-ACCESS-KEY", "KALSHI-ACCESS-SIGNATURE", "KALSHI-ACCESS-TIMESTAMP"}
    assert h["KALSHI-ACCESS-TIMESTAMP"] == "1791750000000"
    # signed message = timestamp + "GET" + "/trade-api/ws/v2"
    assert kalshi_auth.verify(pk.public_key(), h["KALSHI-ACCESS-SIGNATURE"], 1791750000000, "GET", "/trade-api/ws/v2")
    assert not kalshi_auth.verify(pk.public_key(), h["KALSHI-ACCESS-SIGNATURE"], 1791750000000, "GET", "/trade-api/v2/markets")


def test_missing_prod_key_means_feed_off(tmp_path, monkeypatch):
    monkeypatch.setattr(kws, "PROD_KEY_ID_PATH", tmp_path / "nope_id")
    monkeypatch.setattr(kws, "PROD_KEY_PATH", tmp_path / "nope.pem")
    assert not kws.have_prod_credentials()


def test_autotrader_never_uses_prod_paths():
    # the auto-bettor's signer stays pinned to the demo key + demo host
    assert "demo" in str(kalshi_auth.KEY_PATH) and "prod" not in str(kalshi_auth.KEY_PATH)
    with pytest.raises(kalshi_auth.NotDemoError):
        kalshi_auth.assert_demo_url("https://api.elections.kalshi.com/trade-api/v2/portfolio/orders")


# ---------------------------------------------------------------- feed: book -> home mid

def _feed():
    got = []
    f = kws.Feed(targets=lambda: {}, on_quote=lambda *a: got.append(a))
    f.ticker_map = {"H": ("g1", "home"), "A": ("g1", "away")}
    f.connected = True
    return f, got


def test_book_snapshot_delta_mid_and_seq_gap():
    f, got = _feed()
    f.handle(json.dumps({"type": "orderbook_snapshot", "sid": 1, "seq": 1, "msg": {
        "market_ticker": "H", "yes_dollars_fp": [["0.5400", "100.00"], ["0.5500", "10.00"]],
        "no_dollars_fp": [["0.4300", "50.00"]]}}))
    p, d = f.price("g1")
    assert d["src"] == "ws_book" and p == pytest.approx((0.55 + 0.57) / 2)
    f.handle(json.dumps({"type": "orderbook_delta", "sid": 1, "seq": 2, "msg": {
        "market_ticker": "H", "price_dollars": "0.5500", "delta_fp": "-10.00", "side": "yes"}}))
    p, _ = f.price("g1")
    assert p == pytest.approx((0.54 + 0.57) / 2)
    f._flush()
    assert got and got[-1][0] == "g1" and got[-1][3]["src"] == "ws_book"
    with pytest.raises(kws.SeqGap):
        f.handle(json.dumps({"type": "orderbook_delta", "sid": 1, "seq": 5, "msg": {
            "market_ticker": "H", "price_dollars": "0.5400", "delta_fp": "-1.00", "side": "yes"}}))


def test_ticker_and_trade_fallbacks():
    f, _ = _feed()
    f.handle(json.dumps({"type": "ticker", "sid": 2, "msg": {"market_ticker": "A", "yes_bid_dollars": "0.3000",
                                                             "yes_ask_dollars": "0.3200", "price_dollars": "0.3100"}}))
    p, d = f.price("g1")
    assert d["src"] == "ws_ticker_away" and p == pytest.approx(1 - 0.31)
    f2, _ = _feed()
    f2.handle(json.dumps({"type": "trade", "sid": 3, "msg": {"market_ticker": "H", "yes_price_dollars": "0.6100"}}))
    p, d = f2.price("g1")
    assert d["src"] == "ws_trade" and p == pytest.approx(0.61)


def test_fresh_and_lead_measurement(monkeypatch):
    f, _ = _feed()
    assert not f.fresh("g1")
    f.handle(json.dumps({"type": "ticker", "sid": 2, "msg": {"market_ticker": "H", "yes_bid_dollars": "0.5000",
                                                             "yes_ask_dollars": "0.5200"}}))
    f._flush()
    assert f.fresh("g1")
    t_ws = f.emitted["g1"][0]
    f.note_poll("g1", t_ws - 5000, 0.40)
    f.note_poll("g1", t_ws + 1200, 0.51)        # poll catches up to the price the socket had 1.2 s earlier
    assert list(f.leads) == [1200]
    f.connected = False
    assert not f.fresh("g1")


# ---------------------------------------------------------------- two-stage alerts (fake clock)

@pytest.fixture
def eng(monkeypatch):
    from engine import live
    sent = []
    monkeypatch.setitem(live.CFG, "push", True)
    monkeypatch.setitem(live.CFG, "log", False)
    monkeypatch.setitem(live.CFG, "mode", "live")
    monkeypatch.setattr(live.push, "send_all", lambda payload, wait=False: sent.append(payload))
    monkeypatch.setattr(live.autotrader, "on_alert", lambda *a, **k: None)
    monkeypatch.setattr(live, "THRESH", 0.08)
    monkeypatch.setattr(live, "HOLD_MS", 3000)
    monkeypatch.setattr(live, "CALL_DELAY_MS", 8000)
    e = live.Engine()
    T0 = 1_791_700_000_000
    e.update_game({"game_id": "g1", "home": "SEA", "away": "SF", "short_name": "SF @ SEA", "status": "in",
                   "period": 2, "clock": "5:00", "home_score": 7, "away_score": 7, "possession": "SEA",
                   "down": 1, "ydstogo": 10, "yardline_100": 40, "game_seconds_remaining": 2100,
                   "home_id": "26", "away_id": "25"}, T0)
    return live, e, sent, T0


def _run(e, T0, path):
    for t_s, p in path:
        e.on_quote("g1", T0 + int(t_s * 1000), p)


JUMP = [(i, 0.50) for i in range(1, 11)] + [(11, 0.62), (12, 0.62), (13, 0.62), (14, 0.62)]


def test_provisional_then_called_same_id_named(eng, monkeypatch):
    live, e, sent, T0 = eng
    monkeypatch.setattr(live.infer, "infer_play", lambda *a: [{"type": "TD", "team": "SEA", "prob": 0.9},
                                                              {"type": "FG", "team": "SEA", "prob": 0.1}])
    _run(e, T0, JUMP)
    assert len(e.alerts) == 1
    a = e.alerts[0]
    aid = a["id"]
    assert a["stage"] == "provisional" and a["headline"] == "Big swing to the Seahawks"
    assert a["provisional_ms"] == T0 + 14_000 and a["inferred"] == [] and not a["named"]
    assert len(sent) == 1 and sent[0]["tag"] == aid                       # |Δ| 0.12 >= 0.10 -> buzz now
    # an ESPN play arriving during the 8 s window must not grade the provisional alert
    e.on_plays("g1", [{"id": "p1", "type": "TD", "team": "SEA", "text": "TD Seahawks",
                       "wallclock_ms": T0 + 9_000, "seen_ms": T0 + 18_000}], T0 + 18_000, ref_ms=T0 + 18_000)
    assert a["confirmed"] is None and a.get("grade") is None
    _run(e, T0, [(18, 0.62), (22, 0.63)])
    assert len(e.alerts) == 1 and e.alerts[0] is a and a["id"] == aid
    assert a["stage"] == "called" and a["called_ms"] == T0 + 22_000 and a["provisional_ms"] == T0 + 14_000
    assert a["named"] and a["inferred"][0]["type"] == "TD" and "touchdown" in a["headline"]
    alerts_sent = [x for x in sent if not x["title"].startswith("✓")]
    assert len(alerts_sent) == 2 and alerts_sent[1]["tag"] == aid         # same tag: iOS replaces in place
    assert "touchdown" in alerts_sent[1]["body"]
    assert a["confirmed"] and a["grade"] == "correct"                      # graded on the single id
    import time as _t
    _t.sleep(0.2)                                                          # receipt push runs on a thread
    assert all(x["tag"] == aid for x in sent) and sent[-1]["title"].startswith("✓ CONFIRMED")
    assert e.alert_by_id[aid] is a
    # both stages were emitted on the same id
    assert [ev["stage"] for _, ev in e.events if ev["id"] == aid][:2] == ["provisional", "called"]


def test_unnamed_call_does_not_buzz_twice(eng, monkeypatch):
    live, e, sent, T0 = eng
    monkeypatch.setattr(live.infer, "infer_play", lambda *a: [{"type": "OTHER", "team": "SEA", "prob": 0.6}])
    _run(e, T0, JUMP + [(22, 0.62)])
    a = e.alerts[0]
    assert a["stage"] == "called" and not a["named"]
    assert len(sent) == 1 and sent[0]["tag"] == a["id"]                    # stage 1 only


def test_small_swing_no_provisional_push_named_call_pushes(eng, monkeypatch):
    live, e, sent, T0 = eng
    monkeypatch.setattr(live.infer, "infer_play", lambda *a: [{"type": "FG", "team": "SEA", "prob": 0.88}])
    path = [(i, 0.50) for i in range(1, 11)] + [(11, 0.59), (12, 0.59), (13, 0.59), (14, 0.59)]
    _run(e, T0, path)
    a = e.alerts[0]
    assert a["stage"] == "provisional" and a["delta"] == pytest.approx(0.09) and sent == []
    _run(e, T0, [(22, 0.59)])
    assert a["stage"] == "called" and a["named"] and len(sent) == 1 and sent[0]["tag"] == a["id"]


def test_unnamed_small_call_never_pushes(eng, monkeypatch):
    live, e, sent, T0 = eng
    monkeypatch.setattr(live.infer, "infer_play", lambda *a: [{"type": "OTHER", "team": "SEA", "prob": 0.6}])
    path = [(i, 0.50) for i in range(1, 11)] + [(11, 0.59), (12, 0.59), (13, 0.59), (14, 0.59), (22, 0.59)]
    _run(e, T0, path)
    assert e.alerts[0]["stage"] == "called" and sent == []


def test_autotrader_called_once_at_called_stage(eng, monkeypatch):
    live, e, sent, T0 = eng
    calls = []
    monkeypatch.setattr(live.autotrader, "on_alert", lambda a, g=None, **k: calls.append(dict(a)))
    monkeypatch.setattr(live.infer, "infer_play", lambda *a: [{"type": "TD", "team": "SEA", "prob": 0.9}])
    _run(e, T0, JUMP)
    assert calls == []                                                     # provisional never trades
    _run(e, T0, [(22, 0.62), (23, 0.62), (30, 0.62)])
    assert len(calls) == 1 and calls[0]["stage"] == "called" and calls[0]["named"] and calls[0]["id"] == e.alerts[0]["id"]
