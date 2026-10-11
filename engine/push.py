"""Web Push (VAPID) to every subscriber. Works with Apple (web.push.apple.com), FCM, Mozilla.

- Keys: engine/.vapid_private.pem + VAPID_PUBLIC_KEY in engine/.env (run engine/gen_vapid.py once).
- Subscriptions persist to engine/subscriptions.json (gitignored).
- TTL 60, Urgency: high. 404/410 => the subscription is dropped.
"""
from __future__ import annotations

import json
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
    sub = {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"].get("auth", "")},
           "expirationTime": sub.get("expirationTime")}
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


def send_all(payload: dict, wait: bool = False) -> list[dict] | None:
    """Send payload JSON to every subscriber. wait=True blocks and returns per-endpoint results."""
    public_key()  # ensure keys exist
    data = json.dumps(payload)
    subs = load_subs()
    futs = [_pool.submit(_send_one, s, data) for s in subs]
    if wait:
        return [f.result() for f in futs]
    return None


def alert_payload(alert: dict, game: dict | None) -> dict:
    short = (game or {}).get("short_name") or ""
    return {"title": f"SPOILER · {short}".strip(" ·"),
            "body": f"{alert['headline']}. Your stream shows it in ~30s.",
            "url": "./#live", "tag": alert["id"]}
