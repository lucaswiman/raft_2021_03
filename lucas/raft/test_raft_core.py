from raft_core import RaftConfig


def test_leader_append_entries():
    config = RaftConfig(["1", "2"])
    leader, follower = config.build_servers()
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
