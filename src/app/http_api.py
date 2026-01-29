from __future__ import annotations

import json
import random
import ssl
import urllib.request
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from commit_reveal import verify_commitment
from protocol import Move, determine_outcome, is_valid_move
from scoreboard import ScoreBoard
from spiffe_mtls import MtlsFiles, create_client_ssl_context, extract_spiffe_id_from_peer_cert


@dataclass
class MatchRoundState:
    # All identities are SPIFFE IDs in the real mTLS implementation.
    challenger_id: str
    responder_id: str
    commitment: str
    status: str = "challenge_received"
    responder_move: Move | None = None
    challenger_reveal_move: Move | None = None
    challenger_reveal_salt: str | None = None


@dataclass
class InMemoryMatchStore:
    # Keyed by (match_id, round)
    rounds: dict[tuple[str, int], MatchRoundState] = field(default_factory=dict)


@dataclass
class ServerState:
    store: InMemoryMatchStore = field(default_factory=InMemoryMatchStore)
    scoreboard: ScoreBoard = field(default_factory=ScoreBoard)
    server_spiffe_id: str = "spiffe://unknown/server"
    scheme: str = "https"
    default_port: int = 9002
    mtls_files: MtlsFiles | None = None


def run_server(
    *,
    host: str,
    port: int,
    state: ServerState,
    ssl_context: ssl.SSLContext | None = None,
) -> None:
    handler_cls = _make_handler(state)
    httpd = ThreadingHTTPServer((host, port), handler_cls)

    if ssl_context is not None:
        httpd.socket = ssl_context.wrap_socket(httpd.socket, server_side=True)

    state.scheme = "https" if ssl_context is not None else "http"
    state.default_port = port
    print(f"Listening on {state.scheme}://{host}:{port}")
    httpd.serve_forever()


def _make_handler(state: ServerState):
    class Handler(BaseHTTPRequestHandler):
        server_version = "rps/0.1"

        def do_POST(self) -> None:  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                body = json.loads(raw.decode("utf-8")) if raw else {}

                if self.path == "/v1/rps/challenge":
                    self._handle_challenge(body)
                    return
                if self.path == "/v1/rps/response":
                    self._handle_response(body)
                    return
                if self.path == "/v1/rps/reveal":
                    self._handle_reveal(body)
                    return

                self._json_error(HTTPStatus.NOT_FOUND, "not_found", "unknown path")
            except json.JSONDecodeError:
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid_json", "invalid JSON")
            except Exception as exc:  # keep server alive
                self._json_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "server_error",
                    f"{type(exc).__name__}: {exc}",
                )

        # --- Identity helpers ---
        def _peer_spiffe_id(self) -> str:
            # When mTLS is enabled, require the SPIFFE URI SAN from the TLS client certificate.
            if state.mtls_files is not None:
                if not isinstance(self.connection, ssl.SSLSocket):
                    return "spiffe://unauthenticated"
                spiffe_id = extract_spiffe_id_from_peer_cert(self.connection)
                return spiffe_id or "spiffe://unauthenticated"

            # Dev mode (no TLS): explicit header.
            return self.headers.get("X-Debug-Spiffe-Id", "spiffe://unknown/peer")

        def _server_spiffe_id(self) -> str:
            return state.server_spiffe_id

        def _infer_challenger_base_url(self) -> str:
            ip = self.client_address[0]
            return f"{state.scheme}://{ip}:{state.default_port}"

        # --- Handlers ---
        def _handle_challenge(self, body: dict[str, Any]) -> None:
            match_id = body.get("match_id")
            round_no = body.get("round")
            commitment = body.get("commitment")
            if not isinstance(match_id, str) or not isinstance(round_no, int) or not isinstance(commitment, str):
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid_request", "missing/invalid fields")
                return

            challenger_id = self._peer_spiffe_id()
            if state.mtls_files is not None and challenger_id == "spiffe://unauthenticated":
                self._json_error(HTTPStatus.UNAUTHORIZED, "unauthenticated", "mTLS client certificate required")
                return
            responder_id = self._server_spiffe_id()
            key = (match_id, round_no)

            existing = state.store.rounds.get(key)
            if existing is not None:
                if existing.commitment != commitment or existing.challenger_id != challenger_id:
                    self._json_error(HTTPStatus.CONFLICT, "conflict", "challenge already exists with different data")
                    return
                self._json_ok({"match_id": match_id, "round": round_no, "status": "challenge_accepted"})
                return

            state.store.rounds[key] = MatchRoundState(
                challenger_id=challenger_id,
                responder_id=responder_id,
                commitment=commitment,
            )

            # Auto-generate response (message 2) and POST it back to the challenger.
            challenger_url = body.get("challenger_url")
            if not isinstance(challenger_url, str) or not challenger_url:
                challenger_url = self._infer_challenger_base_url()
            responder_move: Move = random.choice(["rock", "paper", "scissors"])  # type: ignore[assignment]
            state.store.rounds[key].responder_move = responder_move

            try:
                client_ctx = None
                if state.mtls_files is not None:
                    client_ctx = create_client_ssl_context(state.mtls_files)
                _post_json(
                    url=f"{challenger_url}/v1/rps/response",
                    payload={"match_id": match_id, "round": round_no, "move": responder_move},
                    headers=None if state.mtls_files is not None else {"X-Debug-Spiffe-Id": responder_id},
                    ssl_context=client_ctx,
                )
            except Exception as exc:
                self._json_error(
                    HTTPStatus.BAD_GATEWAY,
                    "upstream_error",
                    f"failed to POST response to challenger: {type(exc).__name__}: {exc}",
                )
                return

            self._json_ok({"match_id": match_id, "round": round_no, "status": "challenge_accepted"})

        def _handle_response(self, body: dict[str, Any]) -> None:
            match_id = body.get("match_id")
            round_no = body.get("round")
            move = body.get("move")
            if not isinstance(match_id, str) or not isinstance(round_no, int) or not isinstance(move, str):
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid_request", "missing/invalid fields")
                return
            if not is_valid_move(move):
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid_move", "move must be rock|paper|scissors")
                return

            responder_id = self._peer_spiffe_id()
            if state.mtls_files is not None and responder_id == "spiffe://unauthenticated":
                self._json_error(HTTPStatus.UNAUTHORIZED, "unauthenticated", "mTLS client certificate required")
                return
            challenger_id = self._server_spiffe_id()
            key = (match_id, round_no)
            existing = state.store.rounds.get(key)
            if existing is None:
                self._json_error(HTTPStatus.NOT_FOUND, "not_found", "no such match/round")
                return
            if existing.status not in ("challenge_received", "response_received"):
                self._json_error(HTTPStatus.CONFLICT, "conflict", "response not allowed in current state")
                return

            # This endpoint is received by the challenger.
            if existing.challenger_id != challenger_id:
                self._json_error(HTTPStatus.FORBIDDEN, "forbidden", "this server is not the challenger for this match")
                return
            if existing.responder_id != responder_id:
                self._json_error(HTTPStatus.FORBIDDEN, "forbidden", "unexpected responder identity")
                return

            if existing.responder_move is not None and existing.responder_move != move:
                self._json_error(HTTPStatus.CONFLICT, "conflict", "response already exists with different move")
                return

            existing.responder_move = move  # type: ignore[assignment]
            existing.status = "response_received"
            self._json_ok({"match_id": match_id, "round": round_no, "status": "response_accepted"})

        def _handle_reveal(self, body: dict[str, Any]) -> None:
            match_id = body.get("match_id")
            round_no = body.get("round")
            move = body.get("move")
            salt = body.get("salt")
            if not isinstance(match_id, str) or not isinstance(round_no, int) or not isinstance(move, str) or not isinstance(salt, str):
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid_request", "missing/invalid fields")
                return
            if not is_valid_move(move):
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid_move", "move must be rock|paper|scissors")
                return

            challenger_id = self._peer_spiffe_id()
            if state.mtls_files is not None and challenger_id == "spiffe://unauthenticated":
                self._json_error(HTTPStatus.UNAUTHORIZED, "unauthenticated", "mTLS client certificate required")
                return
            key = (match_id, round_no)
            existing = state.store.rounds.get(key)
            if existing is None:
                self._json_error(HTTPStatus.NOT_FOUND, "not_found", "no such match/round")
                return
            if existing.challenger_id != challenger_id:
                self._json_error(HTTPStatus.FORBIDDEN, "forbidden", "only the original challenger can reveal")
                return
            if existing.responder_move is None:
                self._json_error(HTTPStatus.CONFLICT, "conflict", "responder move not recorded yet")
                return

            if existing.status == "revealed":
                if existing.challenger_reveal_move != move or existing.challenger_reveal_salt != salt:
                    self._json_error(HTTPStatus.CONFLICT, "conflict", "reveal already exists with different data")
                    return

            ok = verify_commitment(
                expected_commitment=existing.commitment,
                match_id=match_id,
                round=round_no,
                challenger_spiffe_id=existing.challenger_id,
                responder_spiffe_id=existing.responder_id,
                move=move,  # type: ignore[arg-type]
                salt=salt,
            )
            if not ok:
                self._json_error(HTTPStatus.FORBIDDEN, "commitment_mismatch", "reveal did not match commitment")
                return

            existing.challenger_reveal_move = move  # type: ignore[assignment]
            existing.challenger_reveal_salt = salt
            existing.status = "revealed"

            outcome = determine_outcome(move, existing.responder_move)  # type: ignore[arg-type]
            # Scoreboard is tracked from *this server's* perspective (the responder).
            if outcome == "challenger_win":
                state.scoreboard.record_loss(existing.challenger_id)
            elif outcome == "responder_win":
                state.scoreboard.record_win(existing.challenger_id)

            self._json_ok(
                {
                    "match_id": match_id,
                    "round": round_no,
                    "status": "resolved" if outcome != "tie" else "tie",
                    "outcome": outcome,
                    "challenger_move": move,
                    "responder_move": existing.responder_move,
                }
            )

        # --- Response helpers ---
        def _json_ok(self, payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json_error(self, status: HTTPStatus, code: str, message: str) -> None:
            payload = {"error": code, "message": message}
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # quieter logs; keep one line per request
            print(f"{self.address_string()} {self.command} {self.path} - {format % args}")

    return Handler


def _post_json(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    ssl_context: ssl.SSLContext | None = None,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}
