from __future__ import annotations

import copy, re, queue
from typing import List

import pytest

from raft_core import Message, RaftConfig, RaftServer, compute_majority_match_index
from log import LogEntry
from test_log import FIG_7_EXAMPLES, gen_log


def process_message(server: RaftServer, servers, exclude=None) -> bool:
    try:
        message = server.outgoing_messages.get_nowait()
    except queue.Empty:
        return False
    # Simulate a network roundtrip to exercise serialization/deserialization:
    message = Message.from_bytes(bytes(message))
    if message.recipient_id not in (exclude or ()):
        servers[message.recipient_id].events.put(message)
    return True


def process_event(server: RaftServer, servers, exclude=None) -> bool:
    try:
        event = server.events.get_nowait()
    except queue.Empty:
        return False
    server.process_event(event)
    return True


def do_messages_events(servers: List[RaftServer], max_steps=1000, exclude=None) -> int:
    steps = 0
    while steps < max_steps:
        prev_steps = steps
        for i, server in enumerate(servers):
            if i in (exclude or ()):
                continue
            steps += process_message(server, servers, exclude)
        for i, server in enumerate(servers):
            if i in (exclude or ()):
                continue
            steps += process_event(server, servers, exclude)
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
    assert leader.commit_index == len(leader.log)
    assert leader.application_index == leader.commit_index


class KVStore(dict):
    def __init__(self, queue: queue.Queue[List[dict]]):
        super().__init__()
        self.queue = queue

    def consume_once(self) -> int:
        try:
            items: List[dict] = self.queue.get_nowait()
        except queue.Empty:
            return 0
        for item in items:
            self.update(item)
        return len(items)


def test_kv_store():
    config = RaftConfig([str(i + 1) for i in range(3)])
    leader, *followers = servers = config.build_servers()
    leader.client_add_entry({"foo": "bar"})
    kv_stores = [KVStore(server.applications) for server in servers]

    leader.send_append_entries()
    do_messages_events(servers)
    assert leader.application_index == 1
    assert leader.applications.qsize() == 1
    assert kv_stores[0].consume_once() == 1
    assert kv_stores[0] == {"foo": "bar"}

    for i, follower in enumerate(followers):
        assert follower.application_index == 0
        assert follower.applications.qsize() == 0
        assert kv_stores[i].consume_once() == 0
    leader.send_append_entries()
    do_messages_events(servers)
    for follower, kv_store in zip(followers, kv_stores[1:]):
        assert follower.application_index == 1
        assert follower.applications.qsize() == 1
        assert follower.applications is kv_store.queue
        assert kv_store.consume_once() == 1
        assert kv_store == {"foo": "bar"}


def test_compute_majority_match_index():
    assert compute_majority_match_index([1]) == 1
    assert compute_majority_match_index([1, 2]) == 1
    assert compute_majority_match_index([2, 1]) == 1
    assert compute_majority_match_index([2, 2]) == 2
    assert compute_majority_match_index([1, 1, 3]) == 1
    assert compute_majority_match_index([1, 2, 3]) == 2
    assert compute_majority_match_index([2, 2, 3]) == 2


def test_become_follower_on_higher_term_number():
    config = RaftConfig([str(i + 1) for i in range(2)])
    s1, s2 = servers = config.build_servers()
    assert s1.is_leader
    assert not s2.is_leader
    assert s2.current_term == s1.current_term
    s2.become_candidate()
    assert s2.current_term > s1.current_term
    do_messages_events(servers)
    assert s2.is_leader  # won the election.
    assert not s1.is_leader  # lost the election after receiving a heartbeat.
    assert s1.role == "FOLLOWER"


def test_figure_6_election():
    def build():
        all_entries = copy.deepcopy(FIGURE_6_ENTRIES)
        config = RaftConfig([str(i + 1) for i in range(len(all_entries))])
        servers = config.build_servers()
        for server, entries in zip(servers, all_entries):
            server.log = entries
            server.current_term = max(entry.term for entry in entries)
        return servers

    # Servers 0 and 2 should _always_ win, even if they get all votes.
    for index in [0, 2]:
        servers = build()
        server = servers[index]
        server.become_candidate()
        assert server.role == "CANDIDATE"
        do_messages_events(servers)
        assert server.is_leader

    for index in [1, 3]:
        # These should lose the election, for all subsets of servers.
        servers = build()
        server = servers[index]
        server.become_candidate()
        assert server.role == "CANDIDATE"
        do_messages_events(servers)
        assert server.role == "CANDIDATE"

    # Server 4 can gain a quorum with 1,3:
    servers = build()
    server = servers[4]
    server.become_candidate()
    assert server.role == "CANDIDATE"
    # Simulates a network partition preventing communication with 0, 2.
    do_messages_events(servers, exclude={0, 2})
    assert server.role == "LEADER"

    # But not with 0,2:
    servers = build()
    server = servers[4]
    server.become_candidate()
    assert server.role == "CANDIDATE"
    do_messages_events(servers, exclude={1, 3})
    assert server.role == "CANDIDATE"


def set_up_figure_8_c():
    config = RaftConfig([str(i + 1) for i in range(5)], initial_leader=1)
    s1, s2, s3, s4, s5 = servers = config.build_servers()
    leader = s2
    assert leader.is_leader
    leader.client_add_entry({"x": 1})
    leader.send_append_entries()
    do_messages_events(servers)
    leader.send_append_entries()
    do_messages_events(servers)
    assert [s.commit_index for s in servers] == [1, 1, 1, 1, 1]

    assert leader.commit_index == 1
    for server in servers:
        server.log == [LogEntry(1, {"x": 1})]
    s1.become_candidate()
    do_messages_events(servers)
    leader = s1
    assert leader.is_leader
    leader.client_add_entry({"x": 2})
    leader.send_append_entries()
    # Note the figure 1-indexes the servers, so this is excluding s3, s4, s5.
    do_messages_events(servers, exclude={2, 3, 4})
    assert leader.commit_index == 1

    # The configuration should now be like in figure 8(a).
    # The following assert the conditions of 8(a):
    assert [s.commit_index for s in servers] == [1, 1, 1, 1, 1]
    assert [s.log for s in servers] == [
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1})],
    ]

    # Now construct a sequence of events that leads to 8(b):
    s5.become_candidate()
    # s5 should be elected by a quorum of the s3, s4, s5.
    # They haven't replicated the second log entry.
    do_messages_events(servers, exclude={0, 1})
    assert s5.is_leader
    leader = s5
    assert leader.current_term == 3
    s5.client_add_entry({"x": 3})
    assert [s.commit_index for s in servers] == [1, 1, 1, 1, 1]
    assert [s.log for s in servers] == [
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]
    # Now construct a sequence of events that leads to 8(c):
    leader = s5
    assert leader.is_leader
    s1.become_candidate()
    # Hold an election excluding s4 and s5.
    do_messages_events(servers, exclude={3, 4})
    assert not s1.is_leader
    # s1 lost because it has an out-of-date term.
    s1.become_candidate()  # another election timeout
    do_messages_events(servers, exclude={3, 4})
    assert s1.is_leader
    assert s1.current_term == 4
    s1.send_append_entries()
    do_messages_events(servers, exclude={3, 4})
    s1.send_append_entries()
    do_messages_events(servers, exclude={3, 4})
    s1.client_add_entry({"x": 4})
    assert s1.match_index[s1.id] == len(s1.log)
    assert s1.is_leader
    assert [s.commit_index for s in servers] == [1, 1, 1, 1, 1]
    assert [s.log for s in servers] == [
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]
    return servers


def test_figure_8_e():
    servers = s1, s2, s3, s4, s5 = set_up_figure_8_c()

    # Now get to 8(e):
    s1.send_append_entries()
    do_messages_events(servers, exclude={3, 4})
    s1.send_append_entries()

    do_messages_events(servers, exclude={3, 4})
    assert [s.commit_index for s in servers] == [3, 3, 3, 1, 1]
    assert [s.log for s in servers] == [
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]


def test_figure_8_d():
    servers = s1, s2, s3, s4, s5 = set_up_figure_8_c()
    # Now get to 8(d), wherein s5 will overwrite the values on all of the
    # other servers for terms 2 and 4.

    # s5 should lose the election since it will increment the term number to 4,
    # and voted_for should be set on that term on the other servers. This is
    # why voted_for is listed as non-volatile in Figure 2.
    s5.become_candidate()
    do_messages_events(servers, exclude={0})
    assert s5.role == "CANDIDATE"
    s5.become_candidate()  # another election timeout
    do_messages_events(servers, exclude={0})
    assert s5.is_leader
    s5.send_append_entries()
    do_messages_events(servers)
    assert [s.commit_index for s in servers] == [1, 1, 1, 1, 1]
    assert [s.log for s in servers] == [
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]
