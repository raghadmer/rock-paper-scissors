from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Score:
    wins: int = 0
    losses: int = 0


@dataclass
class ScoreBoard:
    _scores: dict[str, Score] = field(default_factory=dict)
    _path: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> "ScoreBoard":
        p = Path(path)
        if not p.exists():
            return cls(_path=p)
        data = json.loads(p.read_text(encoding="utf-8"))
        scores: dict[str, Score] = {}
        for peer_id, entry in data.get("scores", {}).items():
            if isinstance(entry, dict):
                scores[peer_id] = Score(
                    wins=int(entry.get("wins", 0)),
                    losses=int(entry.get("losses", 0)),
                )
        return cls(_scores=scores, _path=p)

    def save(self) -> None:
        if self._path is None:
            return
        payload = {"scores": {peer: asdict(score) for peer, score in self._scores.items()}}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def record_win(self, peer_spiffe_id: str) -> None:
        score = self._scores.setdefault(peer_spiffe_id, Score())
        score.wins += 1
        self.save()

    def record_loss(self, peer_spiffe_id: str) -> None:
        score = self._scores.setdefault(peer_spiffe_id, Score())
        score.losses += 1
        self.save()

    def get(self, peer_spiffe_id: str) -> Score:
        return self._scores.get(peer_spiffe_id, Score())

    def format_table(self) -> str:
        if not self._scores:
            return "(no games yet)"

        lines: list[str] = []
        header = f"{'peer_spiffe_id':60}  {'wins':>4}  {'losses':>6}"
        lines.append(header)
        lines.append("-" * len(header))
        for peer_id in sorted(self._scores.keys()):
            s = self._scores[peer_id]
            lines.append(f"{peer_id:60}  {s.wins:>4}  {s.losses:>6}")
        return "\n".join(lines)
