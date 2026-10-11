"""The Predator Scale (CONTRACT.md): tier 1-6 for alerts and Dutch Book opportunities."""

TIERS = {
    1: ("Dugar", "Still on the waitlist for his own pre-seed round."),
    2: ("House Cat", "Pre-revenue, pre-product, pre-awake. 'Building in stealth' since 2023."),
    3: ("Gazelle", "Fast, pretty, and somebody's lunch. Series A tourist."),
    4: ("Everyone Else", "A 40-slide consulting deck with no recommendation."),
    5: ("Lion", "Tier-1 partner. Eats the gazelle, takes the board seat."),
    6: ("Kevin & Faisal", "Returned the fund. Twice."),
}


def fields(t: int) -> dict:
    name, blurb = TIERS[t]
    return {"tier": t, "tier_name": name, "tier_blurb": blurb}


def alert_tier(top_prob: float) -> dict:
    p = top_prob or 0.0
    for cut, t in ((0.35, 1), (0.50, 2), (0.65, 3), (0.80, 4), (0.90, 5)):
        if p < cut:
            return fields(t)
    return fields(6)


def dutchbook_tier(opp: dict) -> dict:
    cost = opp.get("cost") or 0
    pa = opp.get("profit_after_fees") or 0
    r = pa / cost if cost else 0
    if r <= 0:
        return fields(1)
    for cut, t in ((0.005, 2), (0.01, 3), (0.02, 4), (0.05, 5)):
        if r < cut:
            return fields(t)
    return fields(6)


def tag_dutchbook(d: dict) -> dict:
    for key in ("opportunities", "near_misses"):
        for o in d.get(key) or []:
            if not o.get("tier"):
                o.update(dutchbook_tier(o))
            elif not o.get("tier_name"):
                o.update(fields(int(o["tier"])))
    return d
