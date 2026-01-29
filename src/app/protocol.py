from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Move = Literal["rock", "paper", "scissors"]
Outcome = Literal["challenger_win", "responder_win", "tie"]


def is_valid_move(value: str) -> bool:
    return value in ("rock", "paper", "scissors")


def determine_outcome(challenger: Move, responder: Move) -> Outcome:
    if challenger == responder:
        return "tie"

    wins = {
        ("rock", "scissors"),
        ("scissors", "paper"),
        ("paper", "rock"),
    }
    return "challenger_win" if (challenger, responder) in wins else "responder_win"


@dataclass(frozen=True)
class Challenge:
    match_id: str
    round: int
    commitment: str


@dataclass(frozen=True)
class Response:
    match_id: str
    round: int
    move: Move


@dataclass(frozen=True)
class Reveal:
    match_id: str
    round: int
    move: Move
    salt: str
