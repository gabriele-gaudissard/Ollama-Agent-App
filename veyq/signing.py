"""Publisher-pinned Ed25519 release manifests; private keys never ship."""
import base64
import hashlib
import json
import re

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

TRUSTED_PUBLIC_KEY = "agoRwsIING5j0pqnSHjrSgeA1/h0AQF0x0ZaEGBucVU="
FIELDS = {"version", "commit", "sequence", "archive_sha256", "files"}


def payload(manifest):
    if not isinstance(manifest, dict) or set(manifest) - {"signature"} != FIELDS:
        raise ValueError("Manifest di aggiornamento non valido.")
    if not re.fullmatch(r"[a-f0-9]{40}", manifest.get("commit", "")):
        raise ValueError("Identificatore versione non valido.")
    if type(manifest["sequence"]) is not int or manifest["sequence"] < 1:
        raise ValueError("Sequenza aggiornamento non valida.")
    if not isinstance(manifest["version"], str) or not re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"]):
        raise ValueError("Versione aggiornamento non valida.")
    hashes = [manifest["archive_sha256"]]
    if not isinstance(manifest["files"], dict) or not 1 <= len(manifest["files"]) <= 100:
        raise ValueError("Elenco file non valido.")
    hashes.extend(manifest["files"].values())
    if any(not isinstance(h, str) or not re.fullmatch(r"[a-f0-9]{64}", h) for h in hashes):
        raise ValueError("Hash aggiornamento non valido.")
    return json.dumps({k: manifest[k] for k in FIELDS}, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def key_id():
    return hashlib.sha256(base64.b64decode(TRUSTED_PUBLIC_KEY, validate=True)).hexdigest()[:16]


def verify_manifest(manifest):
    data = payload(manifest)
    envelope = manifest.get("signature")
    if not isinstance(envelope, dict) or set(envelope) != {"algorithm", "key_id", "value"} or envelope.get("algorithm") != "Ed25519" or envelope.get("key_id") != key_id():
        raise ValueError("Firma del publisher mancante o non riconosciuta.")
    try:
        signature = base64.b64decode(envelope["value"], validate=True)
        Ed25519PublicKey.from_public_bytes(base64.b64decode(TRUSTED_PUBLIC_KEY, validate=True)).verify(signature, data)
    except (InvalidSignature, ValueError, TypeError) as error:
        raise ValueError("Firma aggiornamento non valida. Nessun file installato.") from error


def sign_manifest(manifest, encoded_private_key):
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(encoded_private_key, validate=True))
    public = base64.b64encode(key.public_key().public_bytes_raw()).decode("ascii")
    if public != TRUSTED_PUBLIC_KEY:
        raise ValueError("La chiave di firma non corrisponde al publisher configurato.")
    result = dict(manifest)
    result["signature"] = {"algorithm": "Ed25519", "key_id": key_id(), "value": base64.b64encode(key.sign(payload(manifest))).decode("ascii")}
    return result
