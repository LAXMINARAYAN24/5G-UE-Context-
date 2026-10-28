"""Discrete-event node model, fault channels, independent oracle and recovery.

Times are virtual milliseconds. Faults target application processing/observation,
not arbitrary loss/reordering of reliably delivered SCTP messages.
"""

import random
from dataclasses import asdict, dataclass, field

import simpy

from .model import Context, Snapshot, contradictions
from .verifier import Verifier

SCENARIOS = (
    "clean",
    "delay",
    "loss_request",
    "loss_ack",
    "setup_loss_ack",
    "release_loss_ack",
    "reorder_observations",
    "high_load",
    "observation_outage",
    "idle_resume",
    "intra_gnb",
    "recovery_failure",
)


@dataclass
class Config:
    scenario: str = "loss_ack"
    seed: int = 1
    ues: int = 3
    sessions_per_ue: int = 2
    duration_ms: float = 540.0
    procedure_timeout_ms: float = 110.0
    poll_ms: float = 15.0
    tick_ms: float = 2.0
    grace_ms: float = 12.0
    fixed_ms: float = 25.0
    freshness_ms: float = 60.0
    recovery: bool = False
    recovery_attempts: int = 2
    record_trace: bool = True
    fault_probability: float = 0.7

    def validate(self):
        if self.scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario {self.scenario}")
        if self.ues < 1 or self.sessions_per_ue < 1:
            raise ValueError("At least one UE and session required")
        if (
            min(
                self.duration_ms,
                self.procedure_timeout_ms,
                self.poll_ms,
                self.tick_ms,
                self.freshness_ms,
            )
            <= 0
        ):
            raise ValueError("Time intervals must be positive")
        if min(self.grace_ms, self.fixed_ms, self.recovery_attempts) < 0:
            raise ValueError("Thresholds/attempts cannot be negative")
        if not 0 <= self.fault_probability <= 1:
            raise ValueError("fault_probability must be in [0, 1]")


@dataclass
class Episode:
    key: str
    rule: str
    start: float
    end: float | None = None


@dataclass
class Result:
    config: dict
    mode: str
    alarms: list[dict]
    episodes: list[dict]
    trace: list[dict]
    metrics: dict
    final_states: dict


@dataclass
class Pair:
    ran: Context = field(default_factory=Context)
    core: Context = field(default_factory=Context)
    sequence: dict = field(default_factory=lambda: {"ran": 0, "core": 0})
    published_version: dict = field(default_factory=lambda: {"ran": -1, "core": -1})


class Experiment:
    def __init__(self, config: Config, mode="aware"):
        config.validate()
        self.cfg = config
        self.env = simpy.Environment()
        self.processing_queue = simpy.Resource(self.env, capacity=3)
        self.rng = random.Random(config.seed)
        # Separate observation and recovery RNGs keep node trajectories paired
        # between detector modes and recovery on/off runs until intervention.
        self.obs_rng = random.Random(config.seed + 100000)
        self.rec_rng = random.Random(config.seed + 200000)
        self.verifier = Verifier(mode, config.grace_ms, config.fixed_ms, config.freshness_ms)
        self.pairs = {
            f"ue-{u}/session-{s}": Pair()
            for u in range(config.ues)
            for s in range(1, config.sessions_per_ue + 1)
        }
        self.trace = []
        self.episodes: list[Episode] = []
        self.open_episodes = {}
        self.recovering = set()
        self.recovery_log = []
        self.probes = []
        self.faulted = {key: self.rng.random() < config.fault_probability for key in self.pairs}

    def log(self, key, event, **data):
        if self.cfg.record_trace:
            self.trace.append({"time_ms": self.env.now, "key": key, "event": event, **data})

    def delay(self):
        if self.cfg.scenario == "delay":
            return self.rng.uniform(18, 42)
        return self.rng.uniform(3, 9)

    def publish(self, key, side):
        pair = self.pairs[key]
        context = getattr(pair, side)
        if context.version != pair.published_version[side]:
            context.changed_at = self.env.now
            pair.published_version[side] = context.version
        pair.sequence[side] += 1
        snap = Snapshot(key, side, pair.sequence[side], self.env.now, getattr(pair, side).copy())
        self.env.process(self.deliver_observation(snap))

    def application_leg(self, key, latency):
        yield self.env.timeout(latency)
        if self.cfg.scenario == "high_load":
            queued = self.env.now
            with self.processing_queue.request() as request:
                yield request
                self.log(key, "processing_queue", wait_ms=self.env.now - queued)
                yield self.env.timeout(self.rng.uniform(18, 42))

    def deliver_observation(self, snapshot):
        latency = self.obs_rng.uniform(0.5, 3)
        if self.cfg.scenario == "reorder_observations":
            latency += self.obs_rng.uniform(0, 45)
        if self.cfg.scenario == "observation_outage" and 135 <= self.env.now <= 325:
            self.log(snapshot.key, "observation_dropped", side=snapshot.side)
            return
        yield self.env.timeout(latency)
        self.verifier.ingest(snapshot)
        self.log(
            snapshot.key,
            "observation",
            side=snapshot.side,
            sequence=snapshot.sequence,
            captured_at=snapshot.captured_at,
            **asdict(snapshot.context),
        )

    def poll(self):
        while self.env.now < self.cfg.duration_ms:
            for key in self.pairs:
                self.publish(key, "ran")
                self.publish(key, "core")
            yield self.env.timeout(self.cfg.poll_ms)

    def target_fault(self, key, operation, phase):
        if not self.faulted[key]:
            return False
        scenario = self.cfg.scenario
        expected = {"setup_loss_ack": "setup", "release_loss_ack": "release"}.get(
            scenario, "modify"
        )
        return operation == expected and (
            (scenario == "loss_request" and phase == "request")
            or (
                scenario
                in {
                    "loss_ack",
                    "setup_loss_ack",
                    "release_loss_ack",
                    "recovery_failure",
                    "observation_outage",
                }
                and phase == "ack"
            )
        )

    def procedure(self, key, operation):
        pair = self.pairs[key]
        if operation == "modify" and not pair.core.session:
            self.log(key, "procedure_rejected", operation=operation, reason="no_committed_session")
            return
        if pair.core.pending:
            raise RuntimeError("Overlapping transactions are outside this model")
        pair.core.transaction += 1
        tx = pair.core.transaction
        pair.core.pending = operation
        pair.core.deadline = self.env.now + self.cfg.procedure_timeout_ms
        pair.core.version += 1
        desired_session = operation != "release"
        desired_qos = 1 if operation == "setup" else pair.core.qos + 1
        if operation == "release":
            desired_qos = 0
        self.log(key, "procedure_begin", operation=operation, transaction=tx)
        self.publish(key, "core")
        self.env.process(self.timeout(key, tx))
        request_delay = self.delay()
        ack_delay = self.delay()
        yield self.env.process(self.application_leg(key, request_delay))
        if self.target_fault(key, operation, "request"):
            self.log(key, "application_request_not_processed", operation=operation, transaction=tx)
            return
        if pair.core.transaction != tx or not pair.core.pending:
            self.log(key, "stale_request_rejected", transaction=tx)
            return
        pair.ran.session = desired_session
        pair.ran.resources = desired_session
        pair.ran.qos = desired_qos
        pair.ran.transaction = tx
        pair.ran.version += 1
        self.publish(key, "ran")
        self.log(key, "ran_applied", operation=operation, transaction=tx)
        yield self.env.process(self.application_leg(key, ack_delay))
        if self.target_fault(key, operation, "ack"):
            self.log(
                key, "application_completion_not_processed", operation=operation, transaction=tx
            )
            return
        if pair.core.transaction != tx or not pair.core.pending:
            self.log(key, "stale_completion_rejected", transaction=tx)
            return
        pair.core.session = desired_session
        pair.core.resources = desired_session
        pair.core.qos = desired_qos
        pair.core.pending = ""
        pair.core.version += 1
        self.publish(key, "core")
        self.log(key, "procedure_complete", operation=operation, transaction=tx)

    def timeout(self, key, tx):
        yield self.env.timeout(self.cfg.procedure_timeout_ms)
        core = self.pairs[key].core
        if core.transaction == tx and core.pending:
            operation = core.pending
            core.pending = ""
            core.version += 1
            self.publish(key, "core")
            self.log(key, "procedure_timeout", operation=operation, transaction=tx)

    def lifecycle(self, key, index):
        yield self.env.timeout(10 + index * 2)
        yield self.env.process(self.procedure(key, "setup"))
        yield self.env.timeout(max(0, 145 + index * 2 - self.env.now))
        if self.cfg.scenario == "idle_resume":
            pair = self.pairs[key]
            pair.ran.rrc, pair.ran.resources = "IDLE", False
            pair.core.resources = False  # logical PDU session intentionally retained
            for side in ("ran", "core"):
                getattr(pair, side).version += 1
                self.publish(key, side)
            self.log(key, "access_deactivated_session_retained")
            yield self.env.timeout(35)
            pair.ran.rrc, pair.ran.resources = "CONNECTED", True
            pair.core.resources = True
            for side in ("ran", "core"):
                getattr(pair, side).version += 1
                self.publish(key, side)
            self.log(key, "access_resumed")
        elif self.cfg.scenario == "intra_gnb":
            self.pairs[key].ran.cell = "cell-b"
            self.pairs[key].ran.version += 1
            self.publish(key, "ran")
            self.log(key, "local_cell_changed_core_session_retained")
        else:
            yield self.env.process(self.procedure(key, "modify"))
        yield self.env.timeout(max(0, 350 + index * 2 - self.env.now))
        yield self.env.process(self.procedure(key, "release"))

    def oracle(self):
        """Independent labels from actual nodes; never passed to the verifier."""
        while self.env.now < self.cfg.duration_ms:
            for key, pair in self.pairs.items():
                rules = () if pair.core.pending else contradictions(pair.ran, pair.core)
                for rule in rules:
                    token = (key, rule)
                    if token not in self.open_episodes:
                        episode = Episode(key, rule, self.env.now)
                        self.episodes.append(episode)
                        self.open_episodes[token] = episode
                for token in list(self.open_episodes):
                    if token[0] == key and token[1] not in rules:
                        self.open_episodes.pop(token).end = self.env.now
            yield self.env.timeout(self.cfg.tick_ms)

    def service_probes(self):
        # QoS/session consistency service oracle, not RF or real throughput.
        # Fixed demand times independent of alarm time, avoiding manufactured lead time.
        for time in (285.0, 335.0, 510.0):
            yield self.env.timeout(max(0, time - self.env.now))
            for key, pair in self.pairs.items():
                failed = not pair.core.pending and bool(contradictions(pair.ran, pair.core))
                self.probes.append({"key": key, "time": self.env.now, "failed": failed})
                self.log(key, "service_probe", failed=failed)

    def monitor(self):
        while self.env.now < self.cfg.duration_ms:
            for alarm in self.verifier.check(self.env.now):
                self.log(alarm.key, "alarm", rule=alarm.rule)
                if self.cfg.recovery and alarm.key not in self.recovering:
                    self.recovering.add(alarm.key)
                    self.env.process(self.recover(alarm.key))
            yield self.env.timeout(self.cfg.tick_ms)

    def recover(self, key):
        """Query both nodes, refuse pending/racing writes, reconcile to committed Core.

        This is a custom adapter abstraction, NOT a standardized NGAP command.
        The Core owns committed QoS and resource authorization in this model.
        """
        start = self.env.now
        for attempt in range(1, self.cfg.recovery_attempts + 1):
            self.log(key, "recovery_query", attempt=attempt)
            yield self.env.timeout(self.rec_rng.uniform(5, 10))
            pair = self.pairs[key]
            ran, core = pair.ran.copy(), pair.core.copy()
            if core.pending:
                outcome = "pending_refused"
            elif not contradictions(ran, core):
                outcome = "already_consistent"
            else:
                yield self.env.timeout(self.rec_rng.uniform(5, 10))
                if self.cfg.scenario == "recovery_failure":
                    outcome = "adapter_unavailable"
                elif (pair.core.version, pair.ran.version) != (core.version, ran.version):
                    outcome = "version_changed"
                else:
                    pair.ran.session = core.session
                    pair.ran.resources = core.resources
                    pair.ran.qos = core.qos
                    pair.ran.version += 1
                    self.publish(key, "ran")
                    # Verification uses a second explicit query after actuation.
                    yield self.env.timeout(3)
                    outcome = (
                        "success" if not contradictions(pair.ran, pair.core) else "verify_failed"
                    )
            self.log(key, "recovery_result", attempt=attempt, outcome=outcome)
            if outcome in {"success", "already_consistent"}:
                self.recovery_log.append(
                    {
                        "key": key,
                        "start": start,
                        "end": self.env.now,
                        "attempts": attempt,
                        "outcome": outcome,
                    }
                )
                self.recovering.discard(key)
                return
            yield self.env.timeout(10)
        self.recovery_log.append(
            {
                "key": key,
                "start": start,
                "end": self.env.now,
                "attempts": self.cfg.recovery_attempts,
                "outcome": "exhausted",
            }
        )
        self.log(key, "recovery_exhausted")
        self.recovering.discard(key)

    def run(self) -> Result:
        for index, key in enumerate(self.pairs):
            self.env.process(self.lifecycle(key, index))
        for process in (self.poll, self.oracle, self.monitor, self.service_probes):
            self.env.process(process())
        self.env.run(until=self.cfg.duration_ms)
        for episode in self.open_episodes.values():
            episode.end = self.cfg.duration_ms
        from .metrics import evaluate

        metrics = evaluate(
            self.episodes,
            self.verifier.alarms,
            self.probes,
            self.recovery_log,
            self.cfg.duration_ms,
            len(self.pairs),
            session_keys=self.pairs,
        )
        metrics.update(
            {
                "snapshot_discards": self.verifier.discarded,
                "unknown_checks": self.verifier.unknown_checks,
                "checks": self.verifier.checks,
            }
        )
        return Result(
            asdict(self.cfg),
            self.verifier.mode,
            [asdict(a) for a in self.verifier.alarms],
            [asdict(e) for e in self.episodes],
            self.trace,
            metrics,
            {k: {s: asdict(getattr(p, s)) for s in ("ran", "core")} for k, p in self.pairs.items()},
        )


def run(config: Config, mode="aware") -> Result:
    return Experiment(config, mode).run()
