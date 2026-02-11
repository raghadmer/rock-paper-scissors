from __future__ import annotations

import argparse
import os
import threading
import time
import uuid

from acme_scoreboard import start_acme_scoreboard
from http_api import ServerState, run_server
from move_signing import (
    SignedMove,
    is_signing_available,
    sign_move_sigstore,
    sign_move_ssh,
    create_unsigned_move,
)
from protocol import Move, is_valid_move
from rps_client import send_challenge, send_reveal
from scoreboard import ScoreBoard
from spiffe_mtls import MtlsFiles, create_server_ssl_context, mtls_files_from_cert_dir


# ---------------------------------------------------------------------------
# Interactive command loop — runs in the main thread while the HTTP server
# runs in a background daemon thread.  The player can issue challenges,
# view scores, or quit at any time.  Incoming challenges are handled
# automatically by the server thread (prompting for moves via callback).
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rps",
        description="Interactive Rock-Paper-Scissors with SPIFFE mTLS",
    )
    parser.add_argument("--bind", default="0.0.0.0:9002", help="host:port to listen on")
    parser.add_argument("--spiffe-id", required=True, help="Your SPIFFE ID")
    parser.add_argument("--mtls", action="store_true", help="Enable SPIFFE mTLS")
    parser.add_argument("--cert-dir", default=None, help="Directory with svid.pem, svid_key.pem, svid_bundle.pem")
    parser.add_argument("--scores", default=_default_scores_path(), help="Path to scores JSON file")
    parser.add_argument(
        "--public-url",
        default=None,
        help="Your public URL reachable by peers, e.g. https://<ip>:9002",
    )
    parser.add_argument(
        "--acme-cert",
        default=None,
        help="Path to Let's Encrypt fullchain.pem for public HTTPS scoreboard",
    )
    parser.add_argument(
        "--acme-key",
        default=None,
        help="Path to Let's Encrypt privkey.pem for public HTTPS scoreboard",
    )
    parser.add_argument(
        "--acme-bind",
        default="0.0.0.0:443",
        help="Bind address for the ACME/WebPKI scoreboard (default: 0.0.0.0:443)",
    )
    parser.add_argument(
        "--sign-moves",
        action="store_true",
        help="Cryptographically sign every move (auto-detects Sigstore/SSH)",
    )
    parser.add_argument(
        "--ssh-key",
        default="~/.ssh/id_ed25519",
        help="SSH private key for move signing (default: ~/.ssh/id_ed25519)",
    )

    args = parser.parse_args(argv)

    host, port = _parse_bind(args.bind)
    sb = ScoreBoard.load(args.scores)

    mtls_files: MtlsFiles | None = None
    if args.mtls:
        if not args.cert_dir:
            raise SystemExit("--mtls requires --cert-dir")
        mtls_files = mtls_files_from_cert_dir(args.cert_dir)

    scheme = "https" if mtls_files is not None else "http"

    # Move signing
    signing_method = "none"
    if args.sign_moves:
        signing_method = is_signing_available()
        if signing_method == "none":
            print("WARNING: --sign-moves requested but no signing tool found.")
            print("  Install cosign or create ~/.ssh/id_ed25519 for move signing.")

    state = ServerState(
        scoreboard=sb,
        server_spiffe_id=args.spiffe_id,
        scheme=scheme,
        default_port=port,
        mtls_files=mtls_files,
        prompt_move_callback=_prompt_for_move,
        game_result_callback=_show_game_result,
        signing_method=signing_method,
        ssh_key_path=args.ssh_key,
    )

    # Start HTTP(S) server in background
    ssl_context = create_server_ssl_context(mtls_files) if mtls_files is not None else None
    t = threading.Thread(
        target=run_server,
        kwargs={"host": host, "port": port, "state": state, "ssl_context": ssl_context},
        daemon=True,
    )
    t.start()
    time.sleep(0.5)

    # Start ACME/WebPKI public scoreboard if certs are provided
    acme_info = ""
    if args.acme_cert and args.acme_key:
        acme_host, acme_port = _parse_bind(args.acme_bind)
        start_acme_scoreboard(
            host=acme_host,
            port=acme_port,
            scoreboard=sb,
            server_spiffe_id=args.spiffe_id,
            cert_path=args.acme_cert,
            key_path=args.acme_key,
        )
        acme_info = f"\n  ACME Score : https://{acme_host}:{acme_port}/v1/rps/scores  (WebPKI)"

    challenger_url = args.public_url or f"{scheme}://{_public_bind_host(host)}:{port}"

    print()
    print("=" * 60)
    print("  Rock-Paper-Scissors — Interactive Mode")
    print(f"  SPIFFE ID : {args.spiffe_id}")
    print(f"  Listening : {scheme}://{host}:{port}")
    print(f"  Public URL: {challenger_url}")
    print(f"  Scoreboard: {scheme}://{host}:{port}/v1/rps/scores")
    if signing_method != "none":
        print(f"  Signing   : {signing_method}")
    if acme_info:
        print(acme_info)
    print("=" * 60)
    print()
    print("Commands:")
    print("  challenge <peer_url> <peer_spiffe_id>  — Start a match")
    print("  scores                                 — Show scoreboard")
    print("  help                                   — Show commands")
    print("  quit / exit                            — Exit")
    print()

    # Interactive command loop
    while True:
        try:
            line = input("rps> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return 0

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("Goodbye!")
            return 0

        if cmd in ("scores", "score", "s"):
            print(state.scoreboard.format_table())
            continue

        if cmd in ("help", "h", "?"):
            print("Commands:")
            print("  challenge <peer_url> <peer_spiffe_id>  — Start a match")
            print("  scores                                 — Show scoreboard")
            print("  quit / exit                            — Exit")
            continue

        if cmd in ("challenge", "c", "play"):
            if len(parts) < 3:
                print("Usage: challenge <peer_url> <peer_spiffe_id>")
                print("  Example: challenge https://10.0.0.5:9002 spiffe://raghad.inter-cloud-thi.de/game-server-raghad")
                continue
            peer_url = parts[1]
            peer_id = parts[2]

            # Run the challenge in a thread so the server keeps handling requests
            challenge_thread = threading.Thread(
                target=_run_challenge,
                args=(state, peer_url, peer_id, args.spiffe_id, challenger_url, mtls_files, signing_method, args.ssh_key),
                daemon=True,
            )
            challenge_thread.start()
            continue

        print(f"Unknown command: {cmd}. Type 'help' for available commands.")


def _run_challenge(
    state: ServerState,
    peer_url: str,
    peer_id: str,
    my_spiffe_id: str,
    challenger_url: str,
    mtls_files: MtlsFiles | None,
    signing_method: str = "none",
    ssh_key_path: str = "~/.ssh/id_ed25519",
) -> None:
    """Run a full challenge sequence in a background thread."""
    match_id = str(uuid.uuid4())
    round_no = 1

    move = _prompt_for_challenger_move(round_no)

    while True:
        from http_api import MatchRoundState
        state.store.rounds[(match_id, round_no)] = MatchRoundState(
            challenger_id=my_spiffe_id,
            responder_id=peer_id,
            commitment="",
        )

        try:
            result = send_challenge(
                peer_base_url=peer_url,
                match_id=match_id,
                round=round_no,
                challenger_spiffe_id=my_spiffe_id,
                responder_spiffe_id=peer_id,
                move=move,  # type: ignore[arg-type]
                challenger_url=challenger_url,
                mtls_files=mtls_files,
            )
        except Exception as exc:
            print(f"\n❌ Challenge failed: {exc}")
            print("rps> ", end="", flush=True)
            return

        state.store.rounds[(match_id, round_no)].commitment = result["commitment"]
        salt = result["salt"]
        print(f"Round {round_no}: challenge sent, waiting for response...")

        try:
            _wait_for(
                lambda: state.store.rounds[(match_id, round_no)].responder_move is not None,
                timeout_seconds=60,
            )
        except TimeoutError:
            print("\n⏰ Timed out waiting for peer response.")
            print("rps> ", end="", flush=True)
            return

        # Sign the move before revealing
        signed_move = _sign_move(
            signing_method=signing_method,
            move=move,
            match_id=match_id,
            round_no=round_no,
            signer_spiffe_id=my_spiffe_id,
            ssh_key_path=ssh_key_path,
        )

        try:
            reveal_resp = send_reveal(
                peer_base_url=peer_url,
                match_id=match_id,
                round=round_no,
                move=move,  # type: ignore[arg-type]
                salt=salt,
                challenger_spiffe_id=my_spiffe_id,
                mtls_files=mtls_files,
                signed_move=signed_move,
            )
        except Exception as exc:
            print(f"\n❌ Reveal failed: {exc}")
            print("rps> ", end="", flush=True)
            return

        outcome = reveal_resp.get("outcome", "unknown")
        challenger_move = reveal_resp.get("challenger_move", move)
        responder_move = reveal_resp.get("responder_move", "?")

        print()
        print("=" * 60)
        print(f"  Game Result — Round {round_no}")
        print(f"  Opponent : {peer_id}")
        print(f"  You played: {challenger_move}")
        print(f"  Opponent played: {responder_move}")
        if signed_move.signing_method != "none":
            print(f"  Move signed: ✅ ({signed_move.signing_method})")
        if outcome == "tie":
            print("  Result: 🤝 TIE — replaying...")
        elif outcome == "challenger_win":
            print("  Result: 🎉 YOU WIN!")
            state.scoreboard.record_win(peer_id)
        else:
            print("  Result: 😞 You lose")
            state.scoreboard.record_loss(peer_id)
        print("=" * 60)

        if outcome != "tie":
            break

        round_no += 1
        move = _prompt_for_challenger_move(round_no)

    print()
    print("rps> ", end="", flush=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_move(
    *,
    signing_method: str,
    move: Move,
    match_id: str,
    round_no: int,
    signer_spiffe_id: str,
    ssh_key_path: str = "~/.ssh/id_ed25519",
) -> SignedMove:
    """Sign a move using the configured method."""
    if signing_method == "sigstore":
        try:
            return sign_move_sigstore(
                move=move, match_id=match_id, round=round_no,
                signer_spiffe_id=signer_spiffe_id,
            )
        except Exception as exc:
            print(f"  ⚠ Sigstore signing failed ({exc}), move sent unsigned")
            return create_unsigned_move(
                move=move, match_id=match_id, round=round_no,
                signer_spiffe_id=signer_spiffe_id,
            )
    if signing_method == "ssh":
        try:
            return sign_move_ssh(
                move=move, match_id=match_id, round=round_no,
                signer_spiffe_id=signer_spiffe_id,
                ssh_key_path=ssh_key_path,
            )
        except Exception as exc:
            print(f"  ⚠ SSH signing failed ({exc}), move sent unsigned")
            return create_unsigned_move(
                move=move, match_id=match_id, round=round_no,
                signer_spiffe_id=signer_spiffe_id,
            )
    return create_unsigned_move(
        move=move, match_id=match_id, round=round_no,
        signer_spiffe_id=signer_spiffe_id,
    )


def _wait_for(predicate, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for peer response")


def _parse_bind(bind: str) -> tuple[str, int]:
    if ":" not in bind:
        raise ValueError("--bind must be HOST:PORT")
    host, port_s = bind.rsplit(":", 1)
    return host, int(port_s)


def _default_scores_path() -> str:
    home = os.path.expanduser("~")
    return os.path.join(home, ".rps", "scores.json")


def _public_bind_host(host: str) -> str:
    return "127.0.0.1" if host in ("0.0.0.0", "::") else host


def _prompt_for_move(match_id: str, round_no: int, challenger_id: str) -> Move:
    """Interactive prompt for responder to choose their move (incoming challenge)."""
    print(f"\n🎮 Incoming challenge from {challenger_id}")
    print(f"   Match: {match_id[:8]}..., Round: {round_no}")
    while True:
        choice = input("Your move — (r)ock, (p)aper, (s)cissors: ").strip().lower()
        if choice in ("r", "rock"):
            return "rock"
        if choice in ("p", "paper"):
            return "paper"
        if choice in ("s", "scissors"):
            return "scissors"
        print("❌ Invalid. Enter r, p, or s.")


def _prompt_for_challenger_move(round_no: int) -> Move:
    """Interactive prompt for challenger to choose their move."""
    while True:
        choice = input(f"Round {round_no} — choose (r)ock, (p)aper, (s)cissors: ").strip().lower()
        if choice in ("r", "rock"):
            return "rock"
        if choice in ("p", "paper"):
            return "paper"
        if choice in ("s", "scissors"):
            return "scissors"
        print("❌ Invalid. Enter r, p, or s.")


def _show_game_result(
    match_id: str,
    round_no: int,
    outcome: str,
    challenger_move: Move,
    responder_move: Move,
    challenger_id: str,
) -> None:
    """Display game result for responder (incoming challenge result)."""
    print()
    print("=" * 60)
    print(f"  Game Result — Round {round_no}")
    print(f"  Challenger : {challenger_id}")
    print(f"  Challenger played: {challenger_move}")
    print(f"  You played: {responder_move}")
    if outcome == "tie":
        print("  Result: 🤝 TIE")
    elif outcome == "responder_win":
        print("  Result: 🎉 YOU WIN!")
    else:
        print("  Result: 😞 You lose")
    print("=" * 60)
    print()
    print("rps> ", end="", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
