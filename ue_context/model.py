"""State abstractions, deliberately distinct from wire-level 3GPP state machines."""

from dataclasses import asdict, dataclass


@dataclass
class Context:
    session: bool = False
    resources: bool = False
    qos: int = 0
    rrc: str = "CONNECTED"
    cell: str = "cell-a"
    pending: str = ""
    transaction: int = 0
    deadline: float = 0.0
    version: int = 0
    changed_at: float = 0.0

    def copy(self):
        return Context(**asdict(self))


@dataclass(frozen=True)
class Snapshot:
    key: str
    side: str
    sequence: int
    captured_at: float
    context: Context


def contradictions(ran: Context, core: Context) -> tuple[str, ...]:
    """Compare shared semantics, never RRC enum equality with session enums.

    Core resources means *expected access resources*. A logical session can persist
    while those resources are deactivated. RAN session means retained local context.
    Pending procedures are handled by callers, not this semantic predicate.
    """
    rules = []
    if ran.resources and not core.session:
        rules.append("ORPHAN_RAN_RESOURCE")
    elif ran.resources != core.resources:
        rules.append("ACCESS_RESOURCE_MISMATCH")
    if ran.resources and core.resources and ran.qos != core.qos:
        rules.append("QOS_PROFILE_MISMATCH")
    return tuple(rules)
