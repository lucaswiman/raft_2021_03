------------------------------ MODULE traffic ------------------------------
EXTENDS Integers

\* This is a comment
VARIABLES ew, ns, clock, button

Init == /\ ew = "G"
        /\ ns = "R"
        /\ clock = 0
        /\ button = FALSE

ClockTick == \/ /\ ew = "G"
                /\ ns = "R"
                /\ clock = 29
                /\ ew' = "Y"
                /\ clock' = 0
                /\ UNCHANGED <<ns, button>>
\*             \/ /\ ew = "Y"
\*                /\ ns = "R"
                


ButtonPress == /\ button = FALSE
               /\ button' = TRUE
               /\ UNCHANGED <<ew, ns, clock>>


Next == ClockTick \/ ButtonPress 

=============================================================================
\* Modification History
\* Last modified Tue Mar 23 09:12:11 PDT 2021 by lucaswiman
\* Created Tue Mar 23 08:57:57 PDT 2021 by lucaswiman
