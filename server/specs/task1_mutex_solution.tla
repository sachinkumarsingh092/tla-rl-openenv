---- MODULE mutex_solution ----
EXTENDS Integers

VARIABLES turn, flag, pc

vars == <<turn, flag, pc>>

Init ==
    /\ turn = 0
    /\ flag = [i \in {0, 1} |-> FALSE]
    /\ pc = [i \in {0, 1} |-> "idle"]

Request(i) ==
    /\ pc[i] = "idle"
    /\ flag' = [flag EXCEPT ![i] = TRUE]
    /\ turn' = 1 - i
    /\ pc' = [pc EXCEPT ![i] = "waiting"]

Enter(i) ==
    /\ pc[i] = "waiting"
    /\ (flag[1 - i] = FALSE \/ turn = i)
    /\ pc' = [pc EXCEPT ![i] = "critical"]
    /\ UNCHANGED <<turn, flag>>

Exit(i) ==
    /\ pc[i] = "critical"
    /\ flag' = [flag EXCEPT ![i] = FALSE]
    /\ pc' = [pc EXCEPT ![i] = "idle"]
    /\ UNCHANGED turn

Next ==
    \E i \in {0, 1} :
        \/ Request(i)
        \/ Enter(i)
        \/ Exit(i)

MutualExclusion == ~(pc[0] = "critical" /\ pc[1] = "critical")

Spec == Init /\ [][Next]_vars
====
