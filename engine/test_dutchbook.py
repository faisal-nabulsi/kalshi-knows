from engine.dutchbook import fee, analyze_event, scan


def mk(t, label, ya, na, yq=100, nq=100, **kw):
    d = {"ticker": t, "yes_sub_title": label, "yes_ask_dollars": str(ya), "no_ask_dollars": str(na),
         "yes_ask_size_fp": str(yq), "yes_bid_size_fp": str(nq), "status": "active", "market_type": "binary"}
    d.update(kw)
    return d


def ev(markets, mutex=False, cat="Economics", t="EV-1"):
    return {"event_ticker": t, "series_ticker": "KXTEST", "title": "t", "category": cat,
            "mutually_exclusive": mutex, "markets": markets}


def test_fee_math():
    assert fee(0.5, 100) == 1.75      # 0.07*100*.25 = 1.75
    assert fee(0.55, 100) == 1.74     # 1.7325 -> ceil
    assert fee(0.01, 1) == 0.01       # always rounds up to a cent
    assert fee(0.5, 0) == 0


def test_exhaustive_bracket_arb():
    m = [mk("A", "<70", .20, .81, strike_type="less", cap_strike=70),
         mk("B", "70-79", .30, .71, strike_type="between", floor_strike=70, cap_strike=80),
         mk("C", ">=80", .30, .71, strike_type="greater_or_equal", floor_strike=80)]
    o, n = analyze_event(ev(m, mutex=True))
    assert any(x["kind"] == "exhaustive_set" and x["profit_after_fees"] > 0 for x in o)


def test_ladder_violation():
    m = [mk("L", ">70", .40, .61, strike_type="greater", floor_strike=70),
         mk("H", ">75", .50, .45, strike_type="greater", floor_strike=75)]
    o, _ = analyze_event(ev(m))
    assert any(x["kind"] == "ladder" and abs(x["cost"] - 0.85 * x["legs"][0]["qty"]) < 1e-6 for x in o)


def test_non_exhaustive_false_positive():
    m = [mk("A", "Cardinal A", .30, .72), mk("B", "Cardinal B", .30, .72), mk("C", "Cardinal C", .20, .82)]
    o, n = analyze_event(ev(m, mutex=True))
    assert not any(x["kind"] == "exhaustive_set" for x in o)
    assert any("not" in x["explanation"] and x["kind"] == "exhaustive_set" for x in n)


def test_excluded_and_tier():
    e = ev([mk("A", "x", .2, .81), mk("B", "y", .2, .81)], mutex=True, cat="Politics")
    assert scan([e])["scanned_events"] == 0
    m = [mk("L", ">70", .40, .61, strike_type="greater", floor_strike=70),
         mk("H", ">75", .50, .45, strike_type="greater", floor_strike=75)]
    d = scan([ev(m)])
    assert d["opportunities"] and "tier" in d["opportunities"][0]
