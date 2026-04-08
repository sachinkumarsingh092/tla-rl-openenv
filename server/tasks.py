"""
Task definitions, TLA+ spec templates, and grading logic.

Each task has:
- id, name, difficulty, description
- starting spec (for fix/complete tasks)
- reference solution
- TLC config
- grader function returning (score, feedback)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

try:
    from .tlc_runner import SANYResult, TLCResult, run_sany, run_tlc
except ImportError:
    from server.tlc_runner import SANYResult, TLCResult, run_sany, run_tlc

SPECS_DIR = Path(__file__).parent / "specs"


@dataclass
class TaskDef:
    task_id: str
    name: str
    difficulty: str
    description: str
    starting_spec: str
    reference_solution: str
    tlc_cfg: str
    module_name: str
    max_steps: int
    grader: Callable[[str, "TaskDef"], Tuple[float, str]]


def _read_spec(filename: str) -> str:
    return (SPECS_DIR / filename).read_text()


def _extract_module_name(spec_text: str) -> Optional[str]:
    m = re.search(r"----\s*MODULE\s+(\w+)\s*----", spec_text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Task 1: Fix Syntax Errors in Peterson's Mutex
# ---------------------------------------------------------------------------

TASK1_DESCRIPTION = """Fix the syntax errors in this Peterson's Mutex TLA+ specification.

The spec has TWO syntax errors:
1. One operator definition uses '=' instead of '=='
2. One closing bracket ']' is missing in the Enter action
3. These cause SANY (TLA+ parser) to reject the specification

Your goal: submit a corrected version that parses cleanly AND passes TLC
model checking for the MutualExclusion invariant.

The specification models two processes (0 and 1) competing for a critical
section using Peterson's algorithm with a turn variable and flags."""

TASK1_ERRORS = [
    "Request uses '=' instead of '=='",
    "Enter is missing closing ']' after EXCEPT",
]


def _grade_task1(spec_text: str, task: "TaskDef") -> Tuple[float, str]:
    score = 0.0
    feedback_parts: List[str] = []

    module_name = _extract_module_name(spec_text)
    if not module_name:
        return 0.0, "No MODULE declaration found. TLA+ specs must start with ---- MODULE name ----"

    sany = run_sany(spec_text, module_name)
    if not sany.success:
        n_original = 2
        current_errors = len(sany.errors) if sany.errors else n_original
        improvement = max(0, n_original - current_errors) / n_original
        score = 0.2 * improvement
        feedback_parts.append("SANY parse errors remain:")
        for e in sany.errors[:5]:
            feedback_parts.append(f"  - {e}")
        if sany.raw_output:
            relevant = [
                l for l in sany.raw_output.splitlines()
                if "error" in l.lower() or "line" in l.lower() or "col" in l.lower()
            ][:8]
            if relevant:
                feedback_parts.append("Raw parser output (relevant lines):")
                feedback_parts.extend(f"  {l}" for l in relevant)
        return score, "\n".join(feedback_parts)

    score = 0.4
    feedback_parts.append("Syntax check PASSED (SANY OK).")

    has_request_op = "Request(i) ==" in spec_text or "Request(i)==" in spec_text
    has_enter_bracket = re.search(
        r'EXCEPT\s+!\[i\]\s*=\s*"critical"\s*\]', spec_text
    )
    if has_request_op:
        score += 0.1
    if has_enter_bracket:
        score += 0.1

    tlc = run_tlc(spec_text, task.tlc_cfg, module_name)
    if tlc.success:
        score = 1.0
        feedback_parts.append(
            f"TLC model check PASSED. {tlc.states_found} states explored, "
            f"{tlc.distinct_states} distinct. MutualExclusion holds."
        )
    elif tlc.invariant_violated:
        score = max(score, 0.5)
        feedback_parts.append(
            f"TLC found invariant violation: {tlc.invariant_name}. "
            "The spec parses but the protocol logic may still have issues."
        )
        if tlc.counterexample:
            feedback_parts.append(f"Counterexample:\n{tlc.counterexample[:300]}")
    else:
        score = max(score, 0.4)
        feedback_parts.append("TLC encountered errors:")
        for e in tlc.errors[:3]:
            feedback_parts.append(f"  - {e}")

    return min(score, 1.0), "\n".join(feedback_parts)


# ---------------------------------------------------------------------------
# Task 2: Write Safety Invariant for Token Ring
# ---------------------------------------------------------------------------

TASK2_DESCRIPTION = """Write the MutualExclusion invariant for a Token Ring protocol.

You are given a complete TLA+ specification of a Token Ring protocol with
N processes arranged in a ring. A single token circulates; only the process
holding the token may enter the critical section.

The specification has VARIABLES, Init, Next, and all actions defined.
However, the MutualExclusion invariant is currently set to TRUE (a placeholder).

Your goal: replace the MutualExclusion definition with an invariant that
states "at most one process is in the critical section at any time."

HINT: The variable inCS[i] is TRUE when process i is in the critical section.
The set of processes is Procs == 0..(N-1).

A correct invariant should make TLC verification PASS (no violation found)
with CONSTANT N = 3."""

TRIVIAL_INVARIANTS = {"TRUE", "true", "True"}


def _grade_task2(spec_text: str, task: "TaskDef") -> Tuple[float, str]:
    score = 0.0
    feedback_parts: List[str] = []

    module_name = _extract_module_name(spec_text)
    if not module_name:
        return 0.0, "No MODULE declaration found."

    inv_match = re.search(
        r"MutualExclusion\s*==\s*(.+?)(?:\n\n|\nSpec|\n----|\n====|\Z)",
        spec_text,
        re.DOTALL,
    )
    if not inv_match:
        return 0.05, "No MutualExclusion definition found in the spec."

    inv_body = inv_match.group(1).strip()
    if inv_body in TRIVIAL_INVARIANTS:
        return 0.05, "MutualExclusion is still set to TRUE (the placeholder). Write a real invariant."

    sany = run_sany(spec_text, module_name)
    if not sany.success:
        feedback_parts.append("SANY parse errors:")
        for e in sany.errors[:5]:
            feedback_parts.append(f"  - {e}")
        return 0.15, "\n".join(feedback_parts)

    score = 0.3
    feedback_parts.append("Syntax check PASSED.")

    has_incs_ref = "inCS" in inv_body
    has_quantifier = r"\A" in inv_body or r"\E" in inv_body or "Cardinality" in inv_body
    if has_incs_ref:
        score += 0.05
        feedback_parts.append("Invariant references inCS (good).")
    if has_quantifier:
        score += 0.05
        feedback_parts.append("Invariant uses quantifiers or Cardinality (good).")

    tlc = run_tlc(spec_text, task.tlc_cfg, module_name)
    if tlc.success:
        score = 1.0
        feedback_parts.append(
            f"TLC model check PASSED with N=3. {tlc.states_found} states, "
            f"{tlc.distinct_states} distinct. MutualExclusion invariant verified!"
        )
    elif tlc.invariant_violated:
        score = max(score, 0.3)
        feedback_parts.append(
            f"TLC found invariant VIOLATION: {tlc.invariant_name}. "
            "Your invariant was violated -- it may be too weak or incorrect."
        )
        if tlc.counterexample:
            feedback_parts.append(f"Counterexample:\n{tlc.counterexample[:300]}")
    else:
        feedback_parts.append("TLC errors:")
        for e in tlc.errors[:3]:
            feedback_parts.append(f"  - {e}")

    return min(score, 1.0), "\n".join(feedback_parts)


# ---------------------------------------------------------------------------
# Task 3: Write Two-Phase Commit Spec from Description
# ---------------------------------------------------------------------------

TASK3_DESCRIPTION = """Write a complete TLA+ specification for the Two-Phase Commit protocol.

TWO-PHASE COMMIT PROTOCOL:
- A Transaction Manager (TM) coordinates a set of Resource Managers (RM).
- Each RM starts in a "working" state and can choose to "prepare" or "abort".
- When an RM prepares, it sends a "Prepared" message to the TM.
- The TM collects Prepared messages. Once ALL RMs are prepared, the TM commits.
- If the TM decides to abort, it sends an Abort message.
- RMs that receive a Commit message transition to "committed".
- RMs that receive an Abort message transition to "aborted".

REQUIRED STRUCTURE:
- MODULE name: two_phase_commit
- EXTENDS Integers, FiniteSets
- CONSTANT RM (the set of resource managers)
- VARIABLES: rmState, tmState, tmPrepared, msgs
- Define vars == <<rmState, tmState, tmPrepared, msgs>>
- Init: rmState all "working", tmState = "init", tmPrepared = {}, msgs = {}
- Actions: TMRcvPrepared, TMCommit, TMAbort, RMPrepare, RMChooseToAbort,
           RMRcvCommitMsg, RMRcvAbortMsg
- ConsistencyInvariant: no RM is "committed" while another is "aborted"
- Spec == Init /\\ [][Next]_vars

GRADING: You will be evaluated on parse success, structural completeness,
and TLC verification of ConsistencyInvariant with RM = {r1, r2, r3}."""


TASK3_REQUIRED_COMPONENTS = [
    "rmState",
    "tmState",
    "tmPrepared",
    "msgs",
    "Init",
    "Next",
    "ConsistencyInvariant",
    "TMCommit",
    "TMAbort",
    "RMPrepare",
]


def _grade_task3(spec_text: str, task: "TaskDef") -> Tuple[float, str]:
    score = 0.0
    feedback_parts: List[str] = []

    module_name = _extract_module_name(spec_text)
    if not module_name:
        return 0.0, "No MODULE declaration found. Start with: ---- MODULE two_phase_commit ----"

    sany = run_sany(spec_text, module_name)
    if not sany.success:
        present = [c for c in TASK3_REQUIRED_COMPONENTS if c in spec_text]
        structure_credit = 0.05 * min(len(present) / len(TASK3_REQUIRED_COMPONENTS), 1.0)
        score = structure_credit
        feedback_parts.append("SANY parse FAILED:")
        for e in sany.errors[:5]:
            feedback_parts.append(f"  - {e}")
        feedback_parts.append(
            f"Components found: {', '.join(present)} "
            f"({len(present)}/{len(TASK3_REQUIRED_COMPONENTS)})"
        )
        return score, "\n".join(feedback_parts)

    score = 0.15
    feedback_parts.append("Syntax check PASSED.")

    present = [c for c in TASK3_REQUIRED_COMPONENTS if c in spec_text]
    missing = [c for c in TASK3_REQUIRED_COMPONENTS if c not in spec_text]
    comp_ratio = len(present) / len(TASK3_REQUIRED_COMPONENTS)
    score += 0.15 * comp_ratio

    if missing:
        feedback_parts.append(f"Missing components: {', '.join(missing)}")
    else:
        feedback_parts.append("All required components found.")

    has_invariant = re.search(
        r"ConsistencyInvariant\s*==\s*(.+?)(?:\n\n|\nSpec|\n----|\n====|\Z)",
        spec_text,
        re.DOTALL,
    )
    if not has_invariant or has_invariant.group(1).strip() in TRIVIAL_INVARIANTS:
        feedback_parts.append(
            "ConsistencyInvariant is missing or trivial. "
            "It should state: no RM committed while another aborted."
        )
        return min(score, 0.3), "\n".join(feedback_parts)

    score += 0.1
    feedback_parts.append("ConsistencyInvariant defined (non-trivial).")

    tlc = run_tlc(spec_text, task.tlc_cfg, module_name)
    if tlc.success:
        score = 1.0
        feedback_parts.append(
            f"TLC model check PASSED! {tlc.states_found} states, "
            f"{tlc.distinct_states} distinct. ConsistencyInvariant verified!"
        )
    elif tlc.invariant_violated:
        score = max(score, 0.4)
        feedback_parts.append(
            f"TLC INVARIANT VIOLATION: {tlc.invariant_name}. "
            "The protocol logic or invariant has bugs."
        )
        if tlc.counterexample:
            feedback_parts.append(f"Counterexample:\n{tlc.counterexample[:400]}")
    else:
        score = max(score, 0.3)
        feedback_parts.append("TLC errors (may be structural issues):")
        for e in tlc.errors[:5]:
            feedback_parts.append(f"  - {e}")

    return min(score, 1.0), "\n".join(feedback_parts)


# ---------------------------------------------------------------------------
# Task Registry
# ---------------------------------------------------------------------------

def _load_tasks() -> Dict[str, TaskDef]:
    return {
        "fix_syntax": TaskDef(
            task_id="fix_syntax",
            name="Fix Peterson's Mutex Syntax",
            difficulty="easy",
            description=TASK1_DESCRIPTION,
            starting_spec=_read_spec("task1_mutex_broken.tla"),
            reference_solution=_read_spec("task1_mutex_solution.tla"),
            tlc_cfg=_read_spec("task1_MC.cfg"),
            module_name="mutex_broken",
            max_steps=5,
            grader=_grade_task1,
        ),
        "write_invariant": TaskDef(
            task_id="write_invariant",
            name="Write Token Ring Invariant",
            difficulty="medium",
            description=TASK2_DESCRIPTION,
            starting_spec=_read_spec("task2_token_ring.tla"),
            reference_solution=_read_spec("task2_token_ring_solution.tla"),
            tlc_cfg=_read_spec("task2_MC.cfg"),
            module_name="token_ring",
            max_steps=5,
            grader=_grade_task2,
        ),
        "write_spec": TaskDef(
            task_id="write_spec",
            name="Write Two-Phase Commit Spec",
            difficulty="hard",
            description=TASK3_DESCRIPTION,
            starting_spec="",
            reference_solution=_read_spec("task3_two_phase_commit_solution.tla"),
            tlc_cfg=_read_spec("task3_MC.cfg"),
            module_name="two_phase_commit",
            max_steps=8,
            grader=_grade_task3,
        ),
    }


TASKS: Dict[str, TaskDef] = _load_tasks()
