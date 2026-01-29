from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "src" / "app"
sys.path.insert(0, str(APP_DIR))

from commit_reveal import (  # type: ignore[import-not-found]  # noqa: E402
    SCHEME_ID,
    canonical_string,
    compute_commitment,
    generate_salt,
    verify_commitment,
)
from protocol import determine_outcome  # type: ignore[import-not-found]  # noqa: E402


def test_canonical_string_format() -> None:
    s = canonical_string(
        match_id="m1",
        round=2,
        challenger_spiffe_id="spiffe://a.domain/game-server",
        responder_spiffe_id="spiffe://b.domain/game-server",
        move="rock",
        salt="abc123",
    )
    assert s == (
        f"{SCHEME_ID}|match_id=m1|round=2|"
        "challenger=spiffe://a.domain/game-server|"
        "responder=spiffe://b.domain/game-server|"
        "move=rock|salt=abc123"
    )


def test_commitment_roundtrip() -> None:
    commitment = compute_commitment(
        match_id="m2",
        round=1,
        challenger_spiffe_id="spiffe://a.domain/game-server",
        responder_spiffe_id="spiffe://b.domain/game-server",
        move="paper",
        salt="salt123",
    )
    assert verify_commitment(
        expected_commitment=commitment,
        match_id="m2",
        round=1,
        challenger_spiffe_id="spiffe://a.domain/game-server",
        responder_spiffe_id="spiffe://b.domain/game-server",
        move="paper",
        salt="salt123",
    )


def test_generate_salt_is_b64url_no_padding() -> None:
    salt = generate_salt()
    assert "=" not in salt
    assert re.fullmatch(r"[A-Za-z0-9_-]+", salt)


def test_determine_outcome_matrix() -> None:
    assert determine_outcome("rock", "scissors") == "challenger_win"
    assert determine_outcome("scissors", "paper") == "challenger_win"
    assert determine_outcome("paper", "rock") == "challenger_win"

    assert determine_outcome("scissors", "rock") == "responder_win"
    assert determine_outcome("paper", "scissors") == "responder_win"
    assert determine_outcome("rock", "paper") == "responder_win"

    assert determine_outcome("rock", "rock") == "tie"
