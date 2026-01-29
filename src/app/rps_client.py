from __future__ import annotations

import json
import ssl
import urllib.request
from typing import Any

from commit_reveal import compute_commitment, generate_salt
from protocol import Move
from spiffe_mtls import MtlsFiles, create_client_ssl_context


def send_challenge(
    *,
    peer_base_url: str,
    match_id: str,
    round: int,
    challenger_spiffe_id: str,
    responder_spiffe_id: str,
    move: Move,
    challenger_url: str | None = None,
    mtls_files: MtlsFiles | None = None,
) -> dict[str, Any]:
    salt = generate_salt()
    commitment = compute_commitment(
        match_id=match_id,
        round=round,
        challenger_spiffe_id=challenger_spiffe_id,
        responder_spiffe_id=responder_spiffe_id,
        move=move,
        salt=salt,
    )

    payload: dict[str, Any] = {"match_id": match_id, "round": round, "commitment": commitment}
    if challenger_url:
        payload["challenger_url"] = challenger_url

    # Caller must remember move+salt locally in order to reveal.
    return {
        "challenge": _post_json(peer_base_url + "/v1/rps/challenge", payload, challenger_spiffe_id, mtls_files=mtls_files),
        "salt": salt,
        "commitment": commitment,
    }


def send_reveal(
    *,
    peer_base_url: str,
    match_id: str,
    round: int,
    move: Move,
    salt: str,
    challenger_spiffe_id: str,
    mtls_files: MtlsFiles | None = None,
) -> dict[str, Any]:
    payload = {"match_id": match_id, "round": round, "move": move, "salt": salt}
    return _post_json(peer_base_url + "/v1/rps/reveal", payload, challenger_spiffe_id, mtls_files=mtls_files)


def _post_json(url: str, payload: dict[str, Any], spiffe_id: str, *, mtls_files: MtlsFiles | None = None) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    ssl_context: ssl.SSLContext | None = None
    if mtls_files is not None:
        ssl_context = create_client_ssl_context(mtls_files)
    else:
        # Dev fallback: until SPIFFE mTLS is enabled, pass identity explicitly.
        req.add_header("X-Debug-Spiffe-Id", spiffe_id)

    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}
