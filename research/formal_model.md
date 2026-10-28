# Formal model of the implemented abstraction

The implementation is a timed extended finite-state machine (EFSM), not a complete
3GPP FSM. Its finite control states are augmented with timestamps, transaction IDs,
versions and QoS identifiers. A common simulator clock and complete node telemetry
are assumptions. The Core object combines AMF/SMF roles. N4 and UPF state are not
separately implemented. N2 is control signaling, N3 is the gNB-UPF user plane,
and N4 is SMF-UPF control signaling.

## Local states

RAN resource states: ABSENT (resources=false), APPLIED(q) (resources=true, qos=q).
RRC access state: CONNECTED or IDLE in implemented controls. INACTIVE is not modeled.
Core control states: STABLE, SETUP_PENDING, MODIFY_PENDING, RELEASE_PENDING.
Core committed record: (session, resources, qos). Pending states retain this record
until completion. Initial records are (false,false,0), with RRC CONNECTED because
radio attachment precedes the modeled session workflow.

## Transition relation

| Event and guard | RAN transition | Core transition |
|---|---|---|
| Begin setup, no pending operation | No change | STABLE to SETUP_PENDING, allocate transaction and deadline |
| Begin modify, committed session and no pending operation | No change | STABLE to MODIFY_PENDING, target QoS = old QoS + 1 |
| Begin release, no pending operation | No change | STABLE to RELEASE_PENDING |
| Request processed, transaction current and pending | Apply target (true,true,1) for setup, (true,true,q+1) for modify, (false,false,0) for release | Keep prior committed record |
| Completion processed, transaction current and pending | No change | Commit target record, clear pending |
| Deadline reached, transaction current and pending | Keep applied record | Retain old committed record, clear pending |
| Stale request or completion | Reject without applying | No commit |
| Modify without committed session | No change | Reject |
| Idle control | IDLE, resources=false | Retain logical session, resources=false |
| Resume control | CONNECTED, resources=true | resources=true |
| Local cell control | cell-a to cell-b | No change |
| Recovery, stable and queried versions unchanged | Copy committed Core session/resources/QoS | No change |

The normal lifecycle invokes setup, modification and release sequentially. Idle and
local-cell scenarios substitute their control action for modification. Application
failures are injected at request/completion handling, not as permanent SCTP packet loss.

## Coupling invariants and precedence

| RAN / Core relationship | Interpretation |
|---|---|
| RAN resources=true and Core session=false | ORPHAN_RAN_RESOURCE |
| Resource flags differ, excluding orphan case | ACCESS_RESOURCE_MISMATCH |
| Both resource flags=true and QoS differs | QOS_PROFILE_MISMATCH |
| Both resources=false, logical Core session retained | Valid inactive access |
| RAN local cell differs from Core field | Valid local change, cell equality is not an invariant |
| No predicate holds | Consistent within these three predicates only |

The oracle opens an episode only when Core.pending is empty and a predicate holds.
The verifier sees snapshots, never oracle labels or injected-fault flags. Its evidence
gate requires both sides, monotonically increasing sequence numbers, snapshot age <=
60 ms, and min(capture_R,capture_C) >= max(change_R,change_C). Pending procedures
suppress alarms before their deadline. After a deadline, the monitor requires a Core
snapshot captured at or after it. Accepted contradictory evidence must persist 12 ms.
Stale or incompatible observations reset evidence and represent unknown state.

## Interpretation limits

Timeout alone cannot prove message loss in an unbounded-delay asynchronous system.
This model relies on committed-state telemetry and explicit deadline semantics.
Missing telemetry is unknown, not evidence of consistency. A failed request may
prevent service without causing desynchronization. Recovery can remove orphan
resources without restoring user connectivity. The three probes at 285, 335 and
510 ms measure context consistency, not packet delivery or calls.

With S sessions and a constant three rules, snapshot storage is O(S). The current
checker scans candidate keys inside its session loop and can take O(S squared) work
per tick in the worst case. The six-session benchmark does not establish scalability.
