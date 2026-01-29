from __future__ import annotations

import argparse
import os
import threading
import time
import uuid

from http_api import ServerState, run_server
from protocol import Move, is_valid_move
from rps_client import send_challenge, send_reveal
from scoreboard import ScoreBoard
from spiffe_mtls import MtlsFiles, create_server_ssl_context, mtls_files_from_cert_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rps")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run the HTTP server (mTLS later; HTTP for now)")
    serve.add_argument("--bind", default="0.0.0.0:9002")
    serve.add_argument("--spiffe-id", required=True)
    serve.add_argument("--mtls", action="store_true", help="Enable SPIFFE mTLS using files from --cert-dir")
    serve.add_argument("--cert-dir", default=None, help="Directory containing svid.pem, svid_key.pem, svid_bundle.pem")
    serve.add_argument("--scores", default=_default_scores_path())

    play = sub.add_parser("play", help="Start server and challenge a peer")
    play.add_argument("--bind", default="0.0.0.0:9002")
    play.add_argument("--spiffe-id", required=True)
    play.add_argument("--peer", required=True, help="Peer base URL, e.g. https://1.2.3.4:9002")
    play.add_argument("--peer-id", required=True, help="Expected peer SPIFFE ID")
    play.add_argument("--move", required=True, help="rock|paper|scissors")
    play.add_argument(
        "--public-url",
        default=None,
        help="Your public base URL reachable by peers, e.g. http://<your-public-ip>:9002",
    )
    play.add_argument("--mtls", action="store_true", help="Enable SPIFFE mTLS using files from --cert-dir")
    play.add_argument("--cert-dir", default=None, help="Directory containing svid.pem, svid_key.pem, svid_bundle.pem")
    play.add_argument("--scores", default=_default_scores_path())

    scores = sub.add_parser("scores", help="Print local scores")
    scores.add_argument("--scores", default=_default_scores_path())

    args = parser.parse_args(argv)

    if args.cmd == "scores":
        sb = ScoreBoard.load(args.scores)
        print(sb.format_table())
        return 0

    host, port = _parse_bind(args.bind)
    sb = ScoreBoard.load(args.scores)

    mtls_files: MtlsFiles | None = None
    if getattr(args, "mtls", False):
        if not getattr(args, "cert_dir", None):
            raise SystemExit("--mtls requires --cert-dir")
        mtls_files = mtls_files_from_cert_dir(args.cert_dir)

    state = ServerState(
        scoreboard=sb,
        server_spiffe_id=args.spiffe_id,
        scheme="http",
        default_port=port,
        mtls_files=mtls_files,
    )

    if args.cmd == "serve":
        ssl_context = create_server_ssl_context(mtls_files) if mtls_files is not None else None
        run_server(host=host, port=port, state=state, ssl_context=ssl_context)
        return 0

    if args.cmd == "play":
        move = args.move.strip().lower()
        if not is_valid_move(move):
            raise SystemExit("--move must be rock|paper|scissors")

        # Run the server in the background so the peer can POST /response back.
        ssl_context = create_server_ssl_context(mtls_files) if mtls_files is not None else None
        t = threading.Thread(
            target=run_server,
            kwargs={"host": host, "port": port, "state": state, "ssl_context": ssl_context},
            daemon=True,
        )
        t.start()

        match_id = str(uuid.uuid4())

        # For cross-VM play, peers need a reachable callback URL for message 2.
        # If you don't pass --public-url, we can only work on localhost demos.
        scheme = "https" if mtls_files is not None else "http"
        challenger_url = args.public_url or f"{scheme}://{_public_bind_host(host)}:{port}"

        round_no = 1
        while True:
            # Create local match state so /response can validate identities.
            state.store.rounds[(match_id, round_no)] = __make_local_challenge_state(
                challenger_id=args.spiffe_id,
                responder_id=args.peer_id,
                commitment="",
            )

            # Message 1.
            result = send_challenge(
                peer_base_url=args.peer,
                match_id=match_id,
                round=round_no,
                challenger_spiffe_id=args.spiffe_id,
                responder_spiffe_id=args.peer_id,
                move=move,  # type: ignore[arg-type]
                challenger_url=challenger_url,
                mtls_files=mtls_files,
            )
            state.store.rounds[(match_id, round_no)].commitment = result["commitment"]
            salt = result["salt"]
            print(f"Round {round_no}: challenge sent")

            # Wait for message 2 to arrive.
            _wait_for(lambda: state.store.rounds[(match_id, round_no)].responder_move is not None, timeout_seconds=30)

            # Message 3.
            reveal_resp = send_reveal(
                peer_base_url=args.peer,
                match_id=match_id,
                round=round_no,
                move=move,  # type: ignore[arg-type]
                salt=salt,
                challenger_spiffe_id=args.spiffe_id,
                mtls_files=mtls_files,
            )
            print(f"Round {round_no}: reveal response:", reveal_resp)

            if reveal_resp.get("outcome") != "tie":
                break

            round_no += 1
            # On tie, pick a new move automatically to avoid endless ties.
            import random

            move = random.choice(["rock", "paper", "scissors"])  # type: ignore[assignment]
            print(f"Tie -> starting round {round_no} with move={move}")

        print("Scores:\n" + state.scoreboard.format_table())

        # Keep serving so you can be challenged back.
        print("Server still running. Ctrl+C to exit.")
        while True:
            time.sleep(3600)

    raise SystemExit("unhandled command")


def __make_local_challenge_state(*, challenger_id: str, responder_id: str, commitment: str):
    # Local helper to avoid importing dataclass directly from http_api in CLI.
    from http_api import MatchRoundState

    return MatchRoundState(challenger_id=challenger_id, responder_id=responder_id, commitment=commitment)


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
    # If binding 0.0.0.0, the challenger_url will not be reachable.
    # Users should replace this with their public IP if needed.
    return "127.0.0.1" if host in ("0.0.0.0", "::") else host


if __name__ == "__main__":
    raise SystemExit(main())
