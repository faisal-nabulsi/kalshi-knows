"""Generate the VAPID keypair once (gitignored): engine/.vapid_private.pem + VAPID_PUBLIC_KEY in engine/.env.

Re-running is a no-op unless --force (a new key invalidates every existing subscription).
"""
import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

HERE = Path(__file__).resolve().parent
PEM = HERE / ".vapid_private.pem"
ENV = HERE / ".env"


def public_key_b64(v: Vapid) -> str:
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main():
    force = "--force" in sys.argv
    if PEM.exists() and not force:
        v = Vapid.from_file(str(PEM))
    else:
        v = Vapid()
        v.generate_keys()
        v.save_key(str(PEM))
        PEM.chmod(0o600)
    pub = public_key_b64(v)
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    lines = [ln for ln in lines if not ln.startswith("VAPID_PUBLIC_KEY=")]
    lines.append(f"VAPID_PUBLIC_KEY={pub}")
    ENV.write_text("\n".join(lines) + "\n")
    ENV.chmod(0o600)
    print("VAPID keypair ready (public key is in engine/.env; private key in engine/.vapid_private.pem)")


if __name__ == "__main__":
    main()
