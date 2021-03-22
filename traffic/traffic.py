# traffic.py
#
# Implement traffic light control software.
#
# Challenge: Can you do it with NO dependencies on any runtime environment.
# No threads, no clock, no sockets, no "system" or "runtime" dependencies.
#
# Pure logic/algorithm. Nothing else.
#
# Motivation:  Make something that can be tested/debugged. Debugging
# with threads/sockets is a nightmare.
from queue import Empty, Queue
from typing import NamedTuple, Optional, Literal, Dict
from threading import Thread
from uuid import uuid4
import contextlib


LightColor = Literal["R", "Y", "G"]
LightPosition = Literal["ns", "ew"]
EventType = Literal["timer_done", "pedestrian_button"]


class State(NamedTuple):
    name: str
    ns_color: LightColor
    ew_color: LightColor
    timer_seconds: Optional[int]
    children: Dict[EventType, str]  # maps events to child states.
    keep_timer: bool = (
        False  # Whether an active timer should be kept after the state transition.
    )


# Your task is to write the control software for the traffic light described in this problem. Specifically, here's the light configuration:
#
#     A single East-West light
#     A single North-South light
#     A single push button to change the North-South light to red.
#
# Here are the behaviors that need to be encoded in your controller:
#
#     The East-West light stays green for 30 seconds.
#     The North-South light stays green for 60 seconds.
#     Yellow lights always last 5 seconds.
#     The push-button causes the North-South light to change immediately if it has been green for more than 30 seconds. If less than 30 seconds have elapsed, the light will change once it has been green for 30 seconds.


STATES = {
    # The first 30 seconds of a NS green light. If it receives a pedestrian signal,
    # it will keep the active timer ("the light will change once it has been green
    # for 30 seconds.")
    State(
        "NS_GREEN_LONG",
        ns_color="G",
        ew_color="R",
        timer_seconds=30,
        children={
            "timer_done": "NS_GREEN_SHORT",
            "pedestrian_button": "NS_GREEN_PEDESTRIAN_WAIT",
        },
        keep_timer=True,
    ),
    # The last 30 seconds of a NS green light.
    State(
        "NS_GREEN_SHORT",
        ns_color="G",
        ew_color="R",
        timer_seconds=30,
        children={
            "timer_done": "NS_YELLOW",
            "pedestrian_button": "NS_YELLOW",
        },
    ),
    # Finish out the current timer, then transition to the EW green configuration.
    State(
        "NS_GREEN_PEDESTRIAN_WAIT",
        ns_color="G",
        ew_color="R",
        timer_seconds=None,
        children={
            "timer_done": "NS_YELLOW",
            # Note that if an event is received not in children, then we do nothing,
            # so there is no need to include a pedestrian_button event here.
        },
    ),
    # Yellow lights:
    State(
        "NS_YELLOW",
        ns_color="Y",
        ew_color="R",
        timer_seconds=5,
        children={
            "timer_done": "EW_GREEN",
        },
    ),
    State(
        "EW_YELLOW",
        ns_color="R",
        ew_color="Y",
        timer_seconds=5,
        children={
            "timer_done": "NS_GREEN",
            # "pedestrian_button": TODO? Not mentioned by the spec, but seems
            #                      like you'd want to do something here.
        },
    ),
    State(
        "EW_GREEN",
        ns_color="R",
        ew_color="G",
        timer_seconds=30,
        children={
            "timer_done": "EW_YELLOW",
        },
    ),
}


class StateMachine:
    NAME_TO_STATE = {state.name: state for state in STATES}
    execute_timers = True  # Set to False for debugging / testing.

    def __init__(self, initial_state: str):
        self.current_state = self.NAME_TO_STATE[initial_state]
        self.timer: Optional[Timer] = None

    def start(self):
        self.enter()

    @contextlib.contextmanager
    def lock(self):
        """
        Global lock which happens during state transitions.

        To be implemented in subclasses
        """
        yield

    def enter(self, state_name: str):
        state = self.NAME_TO_STATE[state_name]
        self.set_light_color("ns", state.ns_color)
        self.set_light_color("ew", state.ew_color)
        if state.timer_seconds:
            if not state.keep_timer:
                self.start_timer(state.timer_seconds)
        elif self.timer:
            self.timer.cancel()
            self.timer = None

    def start_timer(self, seconds: int):
        """
        Override in impl class.
        """
        print(f"Starting timer for {seconds}.")
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(seconds)
        if self.execute_timers:
            self.timer.start(self)

    def set_light_color(self, position: LightPosition, color: LightColor):
        """
        Override in impl class.
        """
        print(f"Setting {position} to {color}.")

    def process_event(self, event: EventType, origin=None):
        with self.lock():
            if event == "timer_done" and origin != self.timer:
                # Some previous timer finished, whatevs.
                return
            else:
                next_state: Optional[str] = self.current_state.children.get(event)
                if next_state is None:
                    print("Received invalid transition; ignoring.")
                else:
                    self.enter(next_state)


class Timer:
    def __init__(self, seconds):
        self.seconds = seconds
        self.thread = None
        self.queue = Queue()
        self.uuid = uuid4()

    def do_timer(self, state_machine):
        try:
            # Cheesy way to allow waiting a certain number of seconds or being
            # canceled.
            item = self.queue.get(block=True, timeout=self.seconds)
        except Empty:
            state_machine.process_event("timer_done", origin=self)
        else:
            if item == "cancel":
                pass
            else:
                assert False, f"Got invalid command {item}."

    def cancel(self):
        self.queue.put("cancel")

    def start(self, state_machine):
        self.thread = Thread(target=self.do_timer, args=(state_machine,), daemon=True)
