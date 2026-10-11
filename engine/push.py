"""Web Push (VAPID) to every subscriber. Works with Apple (web.push.apple.com), FCM, Mozilla.

- Keys: engine/.vapid_private.pem + VAPID_PUBLIC_KEY in engine/.env (run engine/gen_vapid.py once).
- Subscriptions persist to engine/subscriptions.json (gitignored).
- TTL 60, Urgency: high. 404/410 => the subscription is dropped.
"""
from __future__ import annotations

import json
import time
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from pywebpush import WebPushException, webpush

HERE = Path(__file__).resolve().parent
PEM = HERE / ".vapid_private.pem"
ENV = HERE / ".env"
SUBS = HERE / "subscriptions.json"
log = logging.getLogger("push")

_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="push")


def _env() -> dict:
    out = {}
    if ENV.exists():
        for ln in ENV.read_text().splitlines():
            if "=" in ln and not ln.strip().startswith("#"):
                k, v = ln.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def public_key() -> str:
    if not PEM.exists() or "VAPID_PUBLIC_KEY" not in _env():
        from engine import gen_vapid
        gen_vapid.main()
    return _env()["VAPID_PUBLIC_KEY"]


def _sub_claim() -> str:
    return os.environ.get("VAPID_SUB") or _env().get("VAPID_SUB") or "mailto:faisalnab25@gmail.com"


def load_subs() -> list[dict]:
    with _lock:
        if SUBS.exists():
            try:
                return json.loads(SUBS.read_text())
            except ValueError:
                return []
        return []


def _save(subs: list[dict]):
    tmp = SUBS.with_suffix(".tmp")
    tmp.write_text(json.dumps(subs, indent=1))
    tmp.replace(SUBS)


PUSH_HOSTS = ("web.push.apple.com", "fcm.googleapis.com", "updates.push.services.mozilla.com",
              "notify.windows.com", "push.services.mozilla.com")


def subscribe(sub: dict) -> int:
    if not isinstance(sub, dict) or not sub.get("endpoint") or not (sub.get("keys") or {}).get("p256dh"):
        raise ValueError("not a PushSubscription (need endpoint + keys.p256dh + keys.auth)")
    from urllib.parse import urlparse
    host = urlparse(sub["endpoint"]).hostname or ""
    if urlparse(sub["endpoint"]).scheme != "https" or not any(host == h or host.endswith("." + h) for h in PUSH_HOSTS):
        raise ValueError("endpoint is not a known browser push service")   # no arbitrary outbound POSTs (SSRF)
    raw_prefs = sub.get("prefs") if isinstance(sub.get("prefs"), dict) else {}
    prefs = {"sync": bool(raw_prefs.get("sync")),
             "delay_s": max(0, min(120, int(float(raw_prefs.get("delay_s") or 48)))),
             "service": str(raw_prefs.get("service") or "")[:24]}
    sub = {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"].get("auth", "")},
           "expirationTime": sub.get("expirationTime"), "prefs": prefs}
    with _lock:
        subs = json.loads(SUBS.read_text()) if SUBS.exists() else []
        subs = [s for s in subs if s.get("endpoint") != sub["endpoint"]]
        subs.append(sub)
        _save(subs)
        return len(subs)


def _drop(endpoint: str):
    with _lock:
        subs = json.loads(SUBS.read_text()) if SUBS.exists() else []
        subs = [s for s in subs if s.get("endpoint") != endpoint]
        _save(subs)


def _send_one(sub: dict, data: str) -> dict:
    ep = sub["endpoint"]
    u = urlparse(ep)
    host = u.netloc
    claims = {"sub": _sub_claim(), "aud": f"{u.scheme}://{u.netloc}"}  # fresh dict per send (pywebpush mutates it)
    try:
        r = webpush(subscription_info={"endpoint": ep, "keys": sub["keys"]}, data=data,
                    vapid_private_key=str(PEM), vapid_claims=claims, ttl=60, timeout=10,
                    headers={"Urgency": "high"})
        code = getattr(r, "status_code", 201)
        return {"host": host, "status": code, "ok": True}
    except WebPushException as e:
        code = getattr(e.response, "status_code", None)
        body = (getattr(e.response, "text", "") or "")[:200]
        if code in (404, 410):
            _drop(ep)
            log.info("dropped expired subscription at %s (%s)", host, code)
        else:
            log.warning("push to %s failed: %s %s", host, code, body)
        return {"host": host, "status": code, "ok": False, "error": body or str(e)[:200]}
    except Exception as e:
        log.warning("push to %s failed: %s", host, e)
        return {"host": host, "status": None, "ok": False, "error": str(e)[:200]}


def send_to(endpoint: str, payload: dict) -> list[dict]:
    """Send to one subscriber (the 'send me a test' button), never the whole audience."""
    public_key()
    subs = [s for s in load_subs() if s.get("endpoint") == endpoint]
    return [_send_one(s, json.dumps(payload)) for s in subs]


def _sync_payload(payload: dict, prefs: dict) -> dict:
    """Version of an alert for a 'sync to my stream' device: lands when their stream shows the play."""
    p = dict(payload)
    svc = prefs.get("service") or "your stream"
    p["title"] = (payload.get("title") or "").replace("SPOILER", "ON YOUR STREAM NOW")
    head = (payload.get("body") or "").split(". Your stream")[0].split(" · Tier")[0]
    p["body"] = f"{head}: happening on {svc} right now."
    return p


def send_all(payload: dict, wait: bool = False) -> list[dict] | None:
    """Send payload JSON to every subscriber. wait=True blocks and returns per-endpoint results.
    Devices in 'sync to my stream' mode get alert pushes scheduled for (estimated play time + their stream delay);
    they skip the provisional stage (the named call arrives when their stream shows the play)."""
    public_key()  # ensure keys exist
    data = json.dumps(payload)
    subs = load_subs()
    now = time.time() * 1000
    futs = []
    for s in subs:
        pr = s.get("prefs") or {}
        if pr.get("sync") and payload.get("play_est_ms"):
            if payload.get("stage") == "provisional":
                continue
            due_ms = payload["play_est_ms"] + pr.get("delay_s", 48) * 1000
            d = json.dumps(_sync_payload(payload, pr))
            wait_s = (due_ms - now) / 1000
            if wait_s > 0.5:
                t = threading.Timer(wait_s, _send_one, args=(s, d)); t.daemon = True; t.start()
                continue
            futs.append(_pool.submit(_send_one, s, d))
            continue
        futs.append(_pool.submit(_send_one, s, data))
    if wait:
        return [f.result() for f in futs]
    return None


def alert_payload(alert: dict, game: dict | None) -> dict:
    short = (game or {}).get("short_name") or ""
    # estimated real-world play time: the price starts moving ~5 s after the play (median market lag 7 s to halfway)
    play_est = (alert.get("jump_started_ms") or alert.get("ts_ms") or 0) - 5000
    return {"title": f"SPOILER · {short}".strip(" ·"),
            "body": f"{alert['headline']}. Your stream shows it in ~30s.",
            "url": "./#live", "tag": alert["id"], "stage": alert.get("stage"), "play_est_ms": play_est}
