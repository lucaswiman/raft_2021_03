import copy, re, queue
from typing import List

import pytest

from raft_core import Message, RaftConfig, RaftServer
from log import LogEntry
from test_log import FIG_7_EXAMPLES, gen_log


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


def PE(s):
    """
    Construct a log entry from the paper's style of entries 1:x<-0.

    PE = Paper Entry
    """
    entries = []
    for entry in s.split(","):
        [(term, var, value)] = re.findall(r"(\d+):(\w+)<-(\d+)", entry)
        entries.append(LogEntry(int(term), {var: value}))
    return entries


FIGURE_6_ENTRIES = [
    PE("1:x<-3,1:y<-1,1:y<-9,2:x<-2,3:x<-0,3:y<-7,3:x<-5,3:x<-4"),
    PE("1:x<-3,1:y<-1,1:y<-9,2:x<-2,3:x<-0"),
    PE("1:x<-3,1:y<-1,1:y<-9,2:x<-2,3:x<-0,3:y<-7,3:x<-5,3:x<-4"),
    PE("1:x<-3,1:y<-1"),
    PE("1:x<-3,1:y<-1,1:y<-9,2:x<-2,3:x<-0,3:y<-7,3:x<-5"),
]


# Since dict order is preserved, the first entry (LEADER) is the first entry here as well.
FIGURE_7_ENTRIES = [gen_log(entries) for entries in FIG_7_EXAMPLES.values()]


@pytest.mark.parametrize(
    "all_entries,leader_term",
    [(FIGURE_6_ENTRIES, 3), (FIGURE_7_ENTRIES, 8)],
)
def test_figures_synchronize(all_entries, leader_term):
    all_entries = copy.deepcopy(all_entries)
    config = RaftConfig([str(i + 1) for i in range(len(all_entries))])
    leader, *followers = servers = config.build_servers()
    for server, entries in zip(servers, all_entries):
        server.log = entries
        server.current_term = max(entry.term for entry in entries)
    leader.current_term = leader_term
    leader.next_index = [len(leader.log) + 1 for _ in servers]
    leader.match_index = [0 if server != leader else len(leader.log) for server in servers]
    leader.send_append_entries()
    do_messages_events(servers)
    for server in servers:
        # Note that in figure 7, (c) has a longer history than the leader,
        # which does not get overwritten when log updates propagate.
        assert len(server.log) >= len(leader.log)
        assert server.log[: len(leader.log)] == leader.log
    # However, once there's a novel entry on the leader, all logs should
    # eventually be the same.
    leader.client_add_entry("foo")
    leader.send_append_entries()
    do_messages_events(servers, max_steps=1000)
    for server in servers:
        assert server.log == leader.log
