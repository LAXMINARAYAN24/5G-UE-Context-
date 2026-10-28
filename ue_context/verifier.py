"""A monitor that only consumes timestamped, complete node snapshots."""

from dataclasses import asdict, dataclass

from .model import Snapshot, contradictions


@dataclass
class Alarm:
    key: str
    time: float
    rule: str
    mismatch_since: float
    ran: dict
    core: dict
    status: str = "detected"


class Verifier:
    def __init__(self, mode="aware", grace_ms=12.0, fixed_ms=25.0, freshness_ms=60.0):
        if mode not in {"immediate", "fixed", "aware"}:
            raise ValueError("mode must be immediate, fixed or aware")
        self.mode = mode
        self.grace = grace_ms
        self.fixed = fixed_ms
        self.freshness = freshness_ms
        self.views: dict[str, dict[str, Snapshot]] = {}
        self.candidates: dict[tuple[str, str], float] = {}
        self.active: set[tuple[str, str]] = set()
        self.alarms: list[Alarm] = []
        self.discarded = 0
        self.unknown_checks = 0
        self.checks = 0

    def ingest(self, snapshot: Snapshot):
        sides = self.views.setdefault(snapshot.key, {})
        previous = sides.get(snapshot.side)
        if previous and snapshot.sequence <= previous.sequence:
            self.discarded += 1
            return
        sides[snapshot.side] = snapshot

    def check(self, now: float) -> list[Alarm]:
        emitted = []
        for key, sides in self.views.items():
            self.checks += 1
            if "ran" not in sides or "core" not in sides:
                self.unknown_checks += 1
                continue
            ran, core = sides["ran"], sides["core"]
            unknown = max(now - ran.captured_at, now - core.captured_at) > self.freshness
            if unknown and self.mode == "aware":
                self.unknown_checks += 1
                # An observation outage breaks evidence of persistent divergence.
                self._clear(key)
                continue
            rules = contradictions(ran.context, core.context)
            if self.mode == "aware" and min(ran.captured_at, core.captured_at) < max(
                ran.context.changed_at, core.context.changed_at
            ):
                # Require overlapping stable observation intervals. Deployment
                # must account for bounded clock skew, unlike the simulator clock.
                self.unknown_checks += 1
                self._clear(key)
                continue
            if self.mode == "aware" and core.context.pending:
                if now < core.context.deadline:
                    self._clear(key)
                    continue
                # Require a post-deadline Core snapshot, rather than extrapolating
                # from an old in-flight state. Polling will supply one when possible.
                if core.captured_at < core.context.deadline:
                    self.unknown_checks += 1
                    self._clear(key)
                    continue
            for candidate in list(self.candidates):
                if candidate[0] == key and candidate[1] not in rules:
                    self.candidates.pop(candidate)
                    self.active.discard(candidate)
            for rule in rules:
                candidate = (key, rule)
                since = self.candidates.setdefault(candidate, now)
                threshold = {"immediate": 0, "fixed": self.fixed, "aware": self.grace}[self.mode]
                if now - since >= threshold and candidate not in self.active:
                    alarm = Alarm(key, now, rule, since, asdict(ran.context), asdict(core.context))
                    self.alarms.append(alarm)
                    emitted.append(alarm)
                    self.active.add(candidate)
        return emitted

    def _clear(self, key):
        for candidate in list(self.candidates):
            if candidate[0] == key:
                self.candidates.pop(candidate)
                self.active.discard(candidate)
