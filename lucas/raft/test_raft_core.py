import queue
from typing import List

from raft_core import Message, RaftConfig, RaftServer


def process_message(server: RaftServer, servers) -> bool:
    try:
        message = server.outgoing_messages.get_nowait()
    except queue.Empty:
        return False
    # Simulate a network roundtrip to exercise serialization/deserialization:
    message = Message.from_bytes(bytes(message))
    servers[message.recipient_id].events.put(message)
    return True


def process_event(server: RaftServer, servers) -> bool:
    try:
        event = server.events.get_nowait()
    except queue.Empty:
        return False
    server.process_event(event)
    return True


def do_messages_events(servers: List[RaftServer], max_steps=1000) -> int:
    steps = 0
    while steps < max_steps:
        prev_steps = steps
        for server in servers:
            steps += process_message(server, servers)
        for server in servers:
            steps += process_event(server, servers)
        if prev_steps == steps:  # did no work
            break
    return steps


def test_leader_append_entries():
    config = RaftConfig(["1", "2"])
    leader, follower = servers = config.build_servers()
    assert len(leader.log) == 0
    leader.client_add_entry("foo")
    assert len(leader.log) == 1
    assert leader.log[0].term == leader.current_term
    assert leader.log[0].item == "foo"
    assert leader.next_index == [2, 1]
    leader.current_term += 1
    leader.client_add_entry("bar")
    assert len(leader.log) == 2
    assert leader.log[1].term == leader.current_term
    assert leader.log[1].item == "bar"
    assert leader.next_index == [3, 1]

    # Nothing to do yet.
    assert do_messages_events(servers) == 0
    leader.send_append_entries()
    assert do_messages_events(servers) > 0
