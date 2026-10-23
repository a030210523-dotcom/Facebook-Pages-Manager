"""Ed25519 license signing (Phase 5 fix to the Phase 1 HMAC design).

Why: with HMAC, the desktop would need the server secret to verify cached licenses —
unacceptable. With Ed25519, the SERVER signs with a private key that never leaves the
server, and the desktop verifies with the PUBLIC key only (safe to ship / pin).
Keys are raw 32-byte, base64-encoded, provided via server env:
  FPM_ED25519_PRIVATE_KEY (server only), public key served at GET /api/license/public-key."""
import base64, json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

def generate_keypair():
    priv = Ed25519PrivateKey.generate()
    raw_priv = priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    raw_pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw_priv).decode(), base64.b64encode(raw_pub).decode()

def _canonical(payload): return json.dumps(payload, sort_keys=True).encode()

def sign_payload_ed(payload, private_key_b64):
    priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    return base64.b64encode(priv.sign(_canonical(payload))).decode()

def verify_payload_ed(payload, signature_b64, public_key_b64):
    try:
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64))
        pub.verify(base64.b64decode(signature_b64), _canonical(payload))
        return True
    except Exception:
        return False

def public_key_from_private(private_key_b64):
    priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(private_key_b64))
    raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()
