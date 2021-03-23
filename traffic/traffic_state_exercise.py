from typing import *

LightColor = Literal["R", "Y", "G"]
EventType = Literal["clock_tick", "button"]


class TrafficLightState(NamedTuple):
    ew: LightColor
    ns: LightColor
    clock: int
    button: bool
    def next_state(self, event: EventType) -> 'TrafficLightState':
        button = self.button
        clock = self.clock
        ew = self.ew
        ns = self.ns
        if event == "clock_tick":
            clock = self.clock + 1
        elif event == "button":
            button = True
        else:
            raise ValueError(event)
        if ns == "G" and ((button and clock >= 30) or (clock >= 60)):
            # Transition immediately since the light has been green for >= 30 seconds.
            return TrafficLightState(
                ew="R",
                ns="Y",
                clock=0,
                button=False,
            )
        elif ew == "G" and clock == 30:
            return TrafficLightState(
                ew="Y",
                ns="R",
                clock=0,
                button=button,
            )
        elif ew == "Y" and clock == 5:
            return TrafficLightState(
                ew="R",
                ns="G",
                clock=0,
                button=button,
            )
        elif ns == "Y" and clock == 5:
            return TrafficLightState(
                ew="G",
                ns="R",
                clock=0,
                button=button,
            )
        else:
            return TrafficLightState(ns=ns, ew=ew, button=button, clock=clock)
    def invariants(self):
        colors = {self.ew, self.ns}
        assert colors <= {"R", "Y", "G"}
        assert self.clock < 60
        if "Y" in colors:
            assert self.clock < 5
        if self.button:
            assert self.clock < 30
        assert len(colors) == 2
        assert colors != {"Y", "G"}


def simulate():
    states = [
        TrafficLightState(ew="R", ns="G", clock=0, button=False),
        TrafficLightState(ew="G", ns="R", clock=0, button=False),
    ]
    seen = set()
    while states:
        print(f"{len(seen)=}")
        state = states.pop()
        print(state)
        state.invariants()
        seen.add(state)
        next_states = {state.next_state(event) for event in ("clock_tick", "button")}
        assert next_states != {state}, f"{next_states} should be different from {state}"
        for next_state in next_states:
            if next_state in seen:
                continue
            states.append(next_state)
    print(len(seen))


if __name__ == "__main__":
    simulate()