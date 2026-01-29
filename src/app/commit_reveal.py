from __future__ import annotations

import hashlib
import secrets
from typing import Final

from protocol import Move

SCHEME_ID: Final[str] = "rps-v1"


def generate_salt(num_bytes: int = 16) -> str:
    # base64url without padding is specified in INTEROP.md, but hex is easier to eyeball.
    # We'll use base64url to match the interop sheet.
    raw = secrets.token_bytes(num_bytes)
    return _b64url_nopad(raw)


def canonical_string(
    *,
    match_id: str,
    round: int,
    challenger_spiffe_id: str,
    responder_spiffe_id: str,
    move: Move,
    salt: str,
) -> str:
    return (
        f"{SCHEME_ID}|match_id={match_id}|round={round}|"
        f"challenger={challenger_spiffe_id}|responder={responder_spiffe_id}|"
        f"move={move}|salt={salt}"
    )


def compute_commitment(
    *,
    match_id: str,
    round: int,
    challenger_spiffe_id: str,
    responder_spiffe_id: str,
    move: Move,
    salt: str,
) -> str:
    payload = canonical_string(
        match_id=match_id,
        round=round,
        challenger_spiffe_id=challenger_spiffe_id,
        responder_spiffe_id=responder_spiffe_id,
        move=move,
        salt=salt,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def verify_commitment(
    *,
    expected_commitment: str,
    match_id: str,
    round: int,
    challenger_spiffe_id: str,
    responder_spiffe_id: str,
    move: Move,
    salt: str,
) -> bool:
    computed = compute_commitment(
        match_id=match_id,
        round=round,
        challenger_spiffe_id=challenger_spiffe_id,
        responder_spiffe_id=responder_spiffe_id,
        move=move,
        salt=salt,
    )
    return secrets.compare_digest(expected_commitment, computed)


def _b64url_nopad(data: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
