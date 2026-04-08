---- MODULE token_ring_solution ----
EXTENDS Integers

CONSTANT N

ASSUME N \in Nat /\ N > 1

VARIABLES hasToken, inCS

vars == <<hasToken, inCS>>

Procs == 0..(N-1)

Init ==
    /\ hasToken = [i \in Procs |-> IF i = 0 THEN TRUE ELSE FALSE]
    /\ inCS = [i \in Procs |-> FALSE]

EnterCS(i) ==
    /\ hasToken[i] = TRUE
    /\ inCS[i] = FALSE
    /\ inCS' = [inCS EXCEPT ![i] = TRUE]
    /\ UNCHANGED hasToken

ExitCS(i) ==
    /\ inCS[i] = TRUE
    /\ inCS' = [inCS EXCEPT ![i] = FALSE]
    /\ UNCHANGED hasToken

PassToken(i) ==
    /\ hasToken[i] = TRUE
    /\ inCS[i] = FALSE
    /\ hasToken' = [hasToken EXCEPT ![i] = FALSE, ![(i + 1) % N] = TRUE]
    /\ UNCHANGED inCS

Next ==
    \E i \in Procs :
        \/ EnterCS(i)
        \/ ExitCS(i)
        \/ PassToken(i)

MutualExclusion == \A i, j \in Procs : (i /= j) => ~(inCS[i] = TRUE /\ inCS[j] = TRUE)

Spec == Init /\ [][Next]_vars
====
