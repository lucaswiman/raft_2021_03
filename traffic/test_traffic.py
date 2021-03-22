from traffic import StateMachine, LightPosition, LightColor

class DebugStateMachine(StateMachine):
    execute_timers = False
    def __init__(self, initial_state: str):
        super().__init__(initial_state)
        self.light_colors = {}
        self.history = []

    def enter(self, state_name: str):
        super().enter(state_name)
        self.history.append(state_name)

    def set_light_color(self, position: LightPosition, color: LightColor):
        """
        Override in impl class.
        """
        self.light_colors[position] = color
    

def test_golden_flow():
    machine = DebugStateMachine("EW_GREEN")
    machine.start()

    # The East-West light stays green for 30 seconds.
    assert machine.timer.seconds == 30
    assert machine.current_state.name == "EW_GREEN"
    
    # Pressing the button should do nothing when the EW light is green.
    machine.process_event("pedestrian_button")
    assert machine.timer.seconds == 30
    assert machine.current_state.name == "EW_GREEN"

    machine.timer.timer_done()
    assert machine.timer.seconds == 5  # Yellow lights always last 5 seconds.
    assert machine.current_state.name == "EW_YELLOW"

    # The push-button causes the North-South light to change immediately if it has been green for more than 30 seconds. If less than 30 seconds have elapsed, the light will change once it has been green for 30 seconds.
    machine.timer.timer_done()
    assert machine.current_state.name == "NS_GREEN_LONG"
    assert machine.timer.seconds == 30
    machine.timer.seconds = 13
    machine.process_event("pedestrian_button")
    assert machine.timer.seconds == 13  # wait the remaining seconds before changing lights.
    assert machine.current_state.name == "NS_GREEN_PEDESTRIAN_WAIT"
    machine.timer.timer_done()
    assert machine.timer.seconds == 5
    assert machine.current_state.name == "NS_YELLOW"
    machine.timer.timer_done()
    assert machine.current_state.name == "EW_GREEN"
    assert machine.timer.seconds == 30
    
    # The North-South light stays green for 60 seconds.
    machine = DebugStateMachine("NS_GREEN_LONG")
    machine.start()
    assert machine.timer.seconds == 30
    assert machine.current_state.name == "NS_GREEN_LONG"
    machine.timer.timer_done()
    assert machine.timer.seconds == 30
    assert machine.current_state.name == "NS_GREEN_SHORT"
    machine.timer.timer_done()
    assert machine.timer.seconds == 5
    assert machine.current_state.name == "NS_YELLOW"
    machine.timer.timer_done()
    assert machine.current_state.name == "EW_GREEN"
    assert machine.timer.seconds == 30
    
def test_immediate_transition_if_less_than_30s():
    machine = DebugStateMachine("NS_GREEN_LONG")
    machine.start()
    assert machine.current_state.name == "NS_GREEN_LONG"
    machine.timer.timer_done()
    assert machine.timer.seconds == 30
    assert machine.current_state.name == "NS_GREEN_SHORT"
    machine.timer.timer_done()
    machine.process_event("pedestrian_button")
    assert machine.current_state.name == "NS_YELLOW"
    assert machine.timer.seconds == 5
    