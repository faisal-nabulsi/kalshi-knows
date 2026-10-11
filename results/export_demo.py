"""Snapshot the auto-bettor's Kalshi DEMO account (play money) for slides/STATS: balance, positions, fills,
and the engine's own order log (which alert triggered which order). Writes results/demo_ledger.json and
results/charts/i_demo_ledger.png. Demo host only (kalshi_auth refuses anything else)."""
import json, sys, time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine import kalshi_auth as A  # noqa: E402

K = A.load_private_key(); KID = A.key_id(); HOST = A.DEMO_BASE.replace("/trade-api/v2", "")


def get(path, params=None):
    A.assert_demo_url(HOST + path)
    r = httpx.get(HOST + path, params=params, headers=A.auth_headers(K, KID, "GET", path), timeout=20)
    r.raise_for_status()
    return r.json()


bal = get("/trade-api/v2/portfolio/balance")
pos = get("/trade-api/v2/portfolio/positions")
fills = get("/trade-api/v2/portfolio/fills", {"limit": 200}).get("fills", [])
orders_log = json.loads((ROOT / "engine/logs/auto/orders.json").read_text()) if (ROOT / "engine/logs/auto/orders.json").exists() else []
demo_orders = [o for o in orders_log if (o.get("demo") or {}).get("order_id")]
out = {
    "as_of": time.strftime("%Y-%m-%d %H:%M %Z"),
    "exchange": "Kalshi DEMO (play money)",
    "balance_usd": float(bal.get("balance_dollars") or bal.get("balance", 0) / 100),
    "portfolio_value_usd": bal.get("portfolio_value"),
    "positions": [{"ticker": p.get("ticker"), "contracts": p.get("position_fp", p.get("position")),
                   "exposure_usd": p.get("market_exposure_dollars"), "realized_pnl_usd": p.get("realized_pnl_dollars")}
                  for p in pos.get("market_positions", [])],
    "fills": [{"ticker": f.get("ticker"), "side": f.get("side"), "action": f.get("action"), "count": f.get("count_fp", f.get("count")),
               "price": f.get("yes_price_dollars") or f.get("price_dollars") or f.get("yes_price"), "created_time": f.get("created_time"),
               "order_id": f.get("order_id")} for f in fills],
    "engine_orders": [{"rule": o.get("rule_id") or o.get("rule"), "ticker": o.get("ticker"), "side": o.get("side"),
                       "count": o.get("count"), "avg_price": o.get("avg_price"), "status": o.get("status"),
                       "trigger": (o.get("trigger") or {}).get("headline") or (o.get("trigger") or {}).get("type"),
                       "order_id": (o.get("demo") or {}).get("order_id"), "ts": o.get("ts") or o.get("created")} for o in demo_orders],
    "manual_test_order": {"order_id": "01a12cc9-43b0-7d31-af6a-b259485bac52", "what": "buy 1 YES 49ers win @ $0.39, fee $0.0167, 2:05pm"},
}
(ROOT / "results/demo_ledger.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: out[k] for k in ("as_of", "balance_usd", "positions")}, indent=1), f"\nfills={len(out['fills'])} engine_orders={len(out['engine_orders'])}")

try:  # a simple slide visual: the order blotter as a table image
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = [[f.get("created_time", "")[11:19], f.get("ticker", "").replace("KXNFLGAME-26OCT11", ""), f.get("action", ""), f.get("side", ""),
             str(f.get("count")), str(f.get("price"))] for f in out["fills"][:12]] or [["—", "no fills yet", "", "", "", ""]]
    fig, ax = plt.subplots(figsize=(16, 9), facecolor="#0A0A0B"); ax.axis("off")
    ax.set_title(f"Auto-bettor orders on Kalshi's demo exchange (play money) · balance ${out['balance_usd']:.2f}", color="#EDE8DF", fontsize=22, loc="left")
    tb = ax.table(cellText=rows, colLabels=["time (UTC)", "market", "action", "side", "contracts", "price"], loc="center", cellLoc="left")
    tb.auto_set_font_size(False); tb.set_fontsize(16); tb.scale(1, 2.2)
    for (r, c), cell in tb.get_celld().items():
        cell.set_facecolor("#14141A" if r else "#FF4D1A"); cell.set_edgecolor("#2A2A30"); cell.get_text().set_color("#EDE8DF" if r else "#0A0A0B")
    fig.savefig(ROOT / "results/charts/i_demo_ledger.png", dpi=100, facecolor="#0A0A0B", bbox_inches="tight")
    print("chart: results/charts/i_demo_ledger.png")
except Exception as e:  # noqa: BLE001
    print("chart skipped:", e)
