"""Kalshi API-key request signing, hard-wired to the DEMO exchange (play money).

Signing per docs.kalshi.com: RSA-PSS (SHA-256, salt = digest length) over
    timestamp_ms + METHOD + path        (path = full URL path incl. /trade-api/v2, NO query string)
sent as KALSHI-ACCESS-KEY / KALSHI-ACCESS-SIGNATURE (base64) / KALSHI-ACCESS-TIMESTAMP.

Safety: DEMO_BASE is a constant. Nothing here reads a base URL from the environment, and
guard_demo_only() refuses to start if any env var smells like the production API.
Credentials only come from KALSHI_DEMO_KEY_ID and ~/.kalshi/demo_private_key.pem. Never printed.
"""
from __future__ import annotations

import base64
import os
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa

DEMO_HOST = "external-api.demo.kalshi.co"          # current official demo host (docs.kalshi.com, Oct 2026)
DEMO_HOSTS = {DEMO_HOST, "demo-api.kalshi.co"}     # legacy demo host also accepted; production never
DEMO_BASE = f"https://{DEMO_HOST}/trade-api/v2"
KEY_PATH = Path(os.path.expanduser("~/.kalshi/demo_private_key.pem"))
_PROD_RE = re.compile(r"(api\.elections\.kalshi\.com|trading-api\.kalshi\.com|(?<!demo-)api\.kalshi\.com|//kalshi\.com)", re.I)


class NotDemoError(RuntimeError):
    pass


def guard_demo_only(environ=None) -> None:
    """Raise if any environment variable points at a non-demo Kalshi host."""
    env = os.environ if environ is None else environ
    for k, v in env.items():
        if k.startswith("KALSHI") and isinstance(v, str) and _PROD_RE.search(v):
            raise NotDemoError(f"refusing to start: env var {k} points at production Kalshi")
        if k.upper() in ("KALSHI_API_BASE", "KALSHI_BASE_URL", "KALSHI_BASE", "KALSHI_API_URL", "KALSHI_ENV") \
                and v and not any(h in v for h in DEMO_HOSTS) and v.lower() != "demo":
            raise NotDemoError(f"refusing to start: {k} is set to something other than the demo exchange")


def assert_demo_url(url: str) -> None:
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in DEMO_HOSTS or not p.path.startswith("/trade-api/v2"):
        raise NotDemoError("signed requests may only target the Kalshi DEMO exchange")


KEY_ID_PATH = Path(os.path.expanduser("~/.kalshi/demo_key_id"))


def key_id() -> str | None:
    v = (os.environ.get("KALSHI_DEMO_KEY_ID") or "").strip()
    if not v and KEY_ID_PATH.is_file():
        v = KEY_ID_PATH.read_text().strip()
    return v or None


def have_credentials() -> bool:
    return bool(key_id()) and KEY_PATH.is_file()


def mask(kid: str | None) -> str:
    return (kid[:4] + "…") if kid else "<none>"


def load_private_key(path: Path | None = None):
    p = Path(path or KEY_PATH)
    return serialization.load_pem_private_key(p.read_bytes(), password=None)


def ephemeral_key():
    """Throwaway key used only to show a structurally valid signature in dry-run previews."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def signature(private_key, timestamp_ms: int | str, method: str, path: str) -> str:
    path = path.split("?")[0]
    msg = f"{timestamp_ms}{method.upper()}{path}".encode()
    if isinstance(private_key, ed25519.Ed25519PrivateKey):      # Ed25519 (Kalshi's recommended key type): sign directly
        sig = private_key.sign(msg)
    else:                                                       # RSA-PSS, SHA-256, salt = digest length
        sig = private_key.sign(msg, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                               hashes.SHA256())
    return base64.b64encode(sig).decode()


def verify(public_key, sig_b64: str, timestamp_ms, method: str, path: str) -> bool:
    from cryptography.exceptions import InvalidSignature
    msg = f"{timestamp_ms}{method.upper()}{path.split('?')[0]}".encode()
    try:
        if isinstance(public_key, ed25519.Ed25519PublicKey):
            public_key.verify(base64.b64decode(sig_b64), msg)
            return True
        public_key.verify(base64.b64decode(sig_b64), msg,
                          padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
                          hashes.SHA256())
        return True
    except InvalidSignature:
        return False


def auth_headers(private_key, kid: str, method: str, path: str, timestamp_ms: int | None = None) -> dict:
    ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    return {"KALSHI-ACCESS-KEY": kid, "KALSHI-ACCESS-SIGNATURE": signature(private_key, ts, method, path),
            "KALSHI-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}


def build_request(method: str, endpoint: str, body: dict | None = None, *, preview: bool = False,
                  timestamp_ms: int | None = None) -> dict:
    """Build the exact signed request for a demo endpoint (endpoint like '/portfolio/orders').
    preview=True: sign with the real key if present, else an ephemeral one; headers are masked."""
    guard_demo_only()
    url = DEMO_BASE + endpoint
    assert_demo_url(url)
    path = urlsplit(url).path
    if have_credentials():
        pk, kid, src = load_private_key(), key_id(), "demo-key"
    elif preview:
        pk, kid, src = ephemeral_key(), "<KALSHI_DEMO_KEY_ID>", "ephemeral-preview-key"
    else:
        raise NotDemoError("no demo credentials")
    h = auth_headers(pk, kid, method, path, timestamp_ms)
    out = {"method": method.upper(), "url": url, "body": body, "headers": h, "signed_with": src}
    if preview:
        out["headers"] = dict(h, **{"KALSHI-ACCESS-KEY": mask(kid) if src == "demo-key" else kid,
                                    "KALSHI-ACCESS-SIGNATURE": h["KALSHI-ACCESS-SIGNATURE"][:24] + "…"})
    return out
