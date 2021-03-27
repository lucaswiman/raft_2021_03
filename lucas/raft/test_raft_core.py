from __future__ import annotations

import copy, random, re, queue
from collections import Counter
from typing import List

import pytest

from raft_core import ClockTick, Message, RaftConfig, RaftNode, compute_majority_match_index
from log import LogEntry
from test_log import FIG_7_EXAMPLES, gen_log


def process_message(node: RaftNode, nodes, exclude=None) -> bool:
    try:
        message = node.outgoing_messages.get_nowait()
    except queue.Empty:
        return False
    # Simulate a network roundtrip to exercise serialization/deserialization:
    message = Message.from_bytes(bytes(message))
    if message.recipient_id not in (exclude or ()):
        nodes[message.recipient_id].events.put(message)
    return True


def process_event(node: RaftNode, nodes, exclude=None) -> bool:
    try:
        event = node.events.get_nowait()
    except queue.Empty:
        return False
    node.process_event(event)
    return True


def do_messages_events(nodes: List[RaftNode], max_steps=1000, exclude=None, max_ticks=0) -> int:
    steps = 0
    executed_ticks = 0
    while (steps < max_steps) and executed_ticks <= max_ticks:
        prev_steps = steps
        for i, node in enumerate(nodes):
            if i in (exclude or ()):
                continue
            steps += process_message(node, nodes, exclude)
        for i, node in enumerate(nodes):
            if i in (exclude or ()):
                continue
            steps += process_event(node, nodes, exclude)
        if executed_ticks < max_ticks:
            for node in nodes:
                steps += 1
                node.process_event(ClockTick())
            executed_ticks += 1
        if prev_steps == steps:  # did no work
            break
    return steps


def test_leader_append_entries():
    config = RaftConfig(["1", "2"])
    leader, follower = nodes = config.build_nodes()
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
    assert do_messages_events(nodes) == 0
    leader.send_append_entries()
    assert do_messages_events(nodes) > 0


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
    leader, *followers = nodes = config.build_nodes()
    for node, entries in zip(nodes, all_entries):
        node.log = entries
        node.current_term = max(entry.term for entry in entries)
    leader.current_term = leader_term
    leader.next_index = [len(leader.log) + 1 for _ in nodes]
    leader.match_index = [0 if node != leader else len(leader.log) for node in nodes]
    leader.send_append_entries()
    do_messages_events(nodes)
    for node in nodes:
        # Note that in figure 7, (c) has a longer history than the leader,
        # which does not get overwritten when log updates propagate.
        assert len(node.log) >= len(leader.log)
        assert node.log[: len(leader.log)] == leader.log
    # However, once there's a novel entry on the leader, all logs should
    # eventually be the same.
    leader.client_add_entry("foo")
    leader.send_append_entries()
    do_messages_events(nodes, max_steps=1000)
    for node in nodes:
        assert node.log == leader.log
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
    leader, *followers = nodes = config.build_nodes()
    leader.client_add_entry({"foo": "bar"})
    kv_stores = [KVStore(node.applications) for node in nodes]

    leader.send_append_entries()
    do_messages_events(nodes)
    assert leader.application_index == 1
    assert leader.applications.qsize() == 1
    assert kv_stores[0].consume_once() == 1
    assert kv_stores[0] == {"foo": "bar"}

    for i, follower in enumerate(followers):
        assert follower.application_index == 0
        assert follower.applications.qsize() == 0
        assert kv_stores[i].consume_once() == 0
    leader.send_append_entries()
    do_messages_events(nodes)
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
    s1, s2 = nodes = config.build_nodes()
    assert s1.is_leader
    assert not s2.is_leader
    assert s2.current_term == s1.current_term
    s2.become_candidate()
    assert s2.current_term > s1.current_term
    do_messages_events(nodes)
    assert s2.is_leader  # won the election.
    assert not s1.is_leader  # lost the election after receiving a heartbeat.
    assert s1.role == "FOLLOWER"


def test_figure_6_election():
    def build():
        all_entries = copy.deepcopy(FIGURE_6_ENTRIES)
        config = RaftConfig([str(i + 1) for i in range(len(all_entries))])
        nodes = config.build_nodes()
        for node, entries in zip(nodes, all_entries):
            node.log = entries
            node.current_term = max(entry.term for entry in entries)
        return nodes

    # Servers 0 and 2 should _always_ win, even if they get all votes.
    for index in [0, 2]:
        nodes = build()
        node = nodes[index]
        node.become_candidate()
        assert node.role == "CANDIDATE"
        do_messages_events(nodes)
        assert node.is_leader

    for index in [1, 3]:
        # These should lose the election, for all subsets of nodes.
        nodes = build()
        node = nodes[index]
        node.become_candidate()
        assert node.role == "CANDIDATE"
        do_messages_events(nodes)
        assert node.role == "CANDIDATE"

    # Server 4 can gain a quorum with 1,3:
    nodes = build()
    node = nodes[4]
    node.become_candidate()
    assert node.role == "CANDIDATE"
    # Simulates a network partition preventing communication with 0, 2.
    do_messages_events(nodes, exclude={0, 2})
    assert node.role == "LEADER"

    # But not with 0,2:
    nodes = build()
    node = nodes[4]
    node.become_candidate()
    assert node.role == "CANDIDATE"
    do_messages_events(nodes, exclude={1, 3})
    assert node.role == "CANDIDATE"


def set_up_figure_8_c():
    config = RaftConfig([str(i + 1) for i in range(5)], initial_leader=1)
    s1, s2, s3, s4, s5 = nodes = config.build_nodes()
    leader = s2
    assert leader.is_leader
    leader.client_add_entry({"x": 1})
    leader.send_append_entries()
    do_messages_events(nodes)
    leader.send_append_entries()
    do_messages_events(nodes)
    assert [s.commit_index for s in nodes] == [1, 1, 1, 1, 1]

    assert leader.commit_index == 1
    for node in nodes:
        node.log == [LogEntry(1, {"x": 1})]
    s1.become_candidate()
    do_messages_events(nodes)
    leader = s1
    assert leader.is_leader
    leader.client_add_entry({"x": 2})
    leader.send_append_entries()
    # Note the figure 1-indexes the nodes, so this is excluding s3, s4, s5.
    do_messages_events(nodes, exclude={2, 3, 4})
    assert leader.commit_index == 1

    # The configuration should now be like in figure 8(a).
    # The following assert the conditions of 8(a):
    assert [s.commit_index for s in nodes] == [1, 1, 1, 1, 1]
    assert [s.log for s in nodes] == [
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
    do_messages_events(nodes, exclude={0, 1})
    assert s5.is_leader
    leader = s5
    assert leader.current_term == 3
    s5.client_add_entry({"x": 3})
    assert [s.commit_index for s in nodes] == [1, 1, 1, 1, 1]
    assert [s.log for s in nodes] == [
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
    do_messages_events(nodes, exclude={3, 4})
    assert not s1.is_leader
    # s1 lost because it has an out-of-date term.
    s1.become_candidate()  # another election timeout
    do_messages_events(nodes, exclude={3, 4})
    assert s1.is_leader
    assert s1.current_term == 4
    s1.send_append_entries()
    do_messages_events(nodes, exclude={3, 4})
    s1.send_append_entries()
    do_messages_events(nodes, exclude={3, 4})
    s1.client_add_entry({"x": 4})
    assert s1.match_index[s1.id] == len(s1.log)
    assert s1.is_leader
    assert [s.commit_index for s in nodes] == [1, 1, 1, 1, 1]
    assert [s.log for s in nodes] == [
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]
    return nodes


def test_figure_8_e():
    nodes = s1, s2, s3, s4, s5 = set_up_figure_8_c()

    # Now get to 8(e):
    s1.send_append_entries()
    do_messages_events(nodes, exclude={3, 4})
    s1.send_append_entries()

    do_messages_events(nodes, exclude={3, 4})
    assert [s.commit_index for s in nodes] == [3, 3, 3, 1, 1]
    assert [s.log for s in nodes] == [
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1}), LogEntry(2, {"x": 2}), LogEntry(4, {"x": 4})],
        [LogEntry(1, {"x": 1})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]


def test_figure_8_d():
    nodes = s1, s2, s3, s4, s5 = set_up_figure_8_c()
    # Now get to 8(d), wherein s5 will overwrite the values on all of the
    # other nodes for terms 2 and 4.

    # s5 should lose the election since it will increment the term number to 4,
    # and voted_for should be set on that term on the other nodes. This is
    # why voted_for is listed as non-volatile in Figure 2.
    s5.become_candidate()
    do_messages_events(nodes, exclude={0})
    assert s5.role == "CANDIDATE"
    s5.become_candidate()  # another election timeout
    do_messages_events(nodes, exclude={0})
    assert s5.is_leader
    s5.send_append_entries()
    do_messages_events(nodes)
    assert [s.commit_index for s in nodes] == [1, 1, 1, 1, 1]
    assert [s.log for s in nodes] == [
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
        [LogEntry(1, {"x": 1}), LogEntry(3, {"x": 3})],
    ]


def tick(node: RaftNode, *, num_clockticks: int = 1):
    for _ in range(num_clockticks):
        node.process_event(ClockTick())


def test_the_concept_of_time():
    random.seed(0)
    config = RaftConfig([str(i + 1) for i in range(5)])
    leader, *followers = nodes = config.build_nodes()
    tick(leader, num_clockticks=leader.clockticks_between_heartbeats - 1)
    assert leader.outgoing_messages.qsize() == 0
    tick(leader)
    assert leader.outgoing_messages.qsize() == 4
    assert leader.clockticks_since_last_reset == 0
    for follower in followers:
        assert follower.role == "FOLLOWER"
        tick(follower, num_clockticks=follower.election_timeout_clockticks - 1)
        assert follower.role == "FOLLOWER"
        assert follower.outgoing_messages.qsize() == 0
        tick(follower)
        assert follower.role == "CANDIDATE"
        assert follower.outgoing_messages.qsize() == 4
        assert follower.current_term == leader.current_term + 1
        assert follower.voted_for == follower.id
    do_messages_events(nodes, max_ticks=0)
    for follower in followers:
        assert follower.role == "CANDIDATE"
        assert follower.voted_for == follower.id
        votes = follower.votes.copy()
        assert leader.id in votes
        votes.pop(leader.id)
        # Everyone should vote for themselves.
        assert votes == {node.id: node.id == follower.id for node in followers}

    # Somebody should win the election.
    do_messages_events(nodes, max_ticks=10_000)
    assert Counter(node.role for node in nodes) == {"LEADER": 1, "FOLLOWER": 4}


def test_votes_among_two_servers_who_are_both_candidates():
    config = RaftConfig([str(i + 1) for i in range(2)])
    nodes = config.build_nodes()
    for node in nodes:
        node.become_candidate()
    do_messages_events(nodes, max_ticks=1)
    breakpoint()
