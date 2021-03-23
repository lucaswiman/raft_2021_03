from log import LogEntry, append_entries as orig_append_entries, Log

import pytest


def append_entries(log, *args, **kwargs):
    """
    Runs append_entries, and asserts idempotence.
    """
    new_log = list(log)
    success = orig_append_entries(new_log, *args, **kwargs)
    if success:
        prev = list(new_log)
        assert orig_append_entries(new_log, *args, **kwargs)  # should succeed again
        # but not mutate the log
        assert new_log == prev
    else:
        # Failures should never mutate the log.
        assert new_log == log
    return orig_append_entries(log, *args, **kwargs)


def test_append_valid():
    log = []
    entries = [
        LogEntry(1, "x"),
        LogEntry(1, "y"),
        LogEntry(2, "z"),
    ]
    for i, entry in enumerate(entries, 1):
        prev_index = i - 1
        if prev_index == 0:
            prev_term = 0
        else:
            prev_term = log[prev_index - 1].term
        assert append_entries(log=log, prev_index=prev_index, prev_term=prev_term, entries=[entry])
        assert log == entries[:i]


def test_append_noops():
    orig_log = [
        LogEntry(1, "x"),
        LogEntry(1, "y"),
        LogEntry(2, "z"),
    ]
    log = list(orig_log)
    assert append_entries(log=log, prev_index=0, prev_term=0, entries=[])
    assert log == orig_log
    assert append_entries(log=log, prev_index=0, prev_term=0, entries=orig_log[0:1])
    assert log == orig_log
    assert append_entries(log=log, prev_index=0, prev_term=0, entries=orig_log[0:2])
    assert log == orig_log
    assert append_entries(log=log, prev_index=0, prev_term=0, entries=orig_log[0:3])
    assert log == orig_log

    assert append_entries(log=log, prev_index=1, prev_term=1, entries=[])
    assert log == orig_log
    assert append_entries(log=log, prev_index=1, prev_term=1, entries=orig_log[1:2])
    assert log == orig_log
    assert append_entries(log=log, prev_index=1, prev_term=1, entries=orig_log[1:3])
    assert log == orig_log

    assert append_entries(log=log, prev_index=2, prev_term=1, entries=[])
    assert log == orig_log
    assert append_entries(log=log, prev_index=3, prev_term=2, entries=[])
    assert log == orig_log


def test_append_deletes_subsequent_entries():
    log = [
        LogEntry(1, "x"),
        LogEntry(1, "y"),
        LogEntry(2, "z"),
    ]
    append_entries(log=log, prev_index=0, prev_term=0, entries=[LogEntry(10, "foo")])
    assert log == [LogEntry(10, "foo")]
    log = [
        LogEntry(1, "x"),
        LogEntry(1, "y"),
        LogEntry(2, "z"),
    ]
    append_entries(log=log, prev_index=1, prev_term=1, entries=[LogEntry(10, "foo")])
    assert log == [LogEntry(1, "x"), LogEntry(10, "foo")]


# From figure 7 in the raft paper.
FIG_7_EXAMPLES = {
    "LEADER": (1, 1, 1, 4, 4, 5, 5, 6, 6, 6),
    "a": (1, 1, 1, 4, 4, 5, 5, 6, 6),
    "b": (1, 1, 1, 4),
    "c": (1, 1, 1, 4, 4, 5, 5, 6, 6, 6, 6),
    "d": (1, 1, 1, 4, 4, 5, 5, 6, 6, 6, 7, 7),
    "e": (1, 1, 1, 4, 4, 4, 4),
    "f": (1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3),
}


def gen_log(term_numbers) -> Log:
    return [LogEntry(term, term) for term in term_numbers]


@pytest.mark.parametrize(
    "example,expected_index",
    [("a", 10), ("b", 5), ("c", 11), ("d", 11), ("e", 6), ("f", 4)],
)
def test_figure_7(example, expected_index):
    """
    Tests that starting from the right index, an update from the leader will
    succeed at the expected_index-th index.
    """
    leader = gen_log(FIG_7_EXAMPLES["LEADER"]) + [LogEntry(term=8, item=8)]
    first_succeeded_at = None
    for i in reversed(range(1, len(leader) + 1)):
        follower = gen_log(FIG_7_EXAMPLES[example])
        expected_success = i <= expected_index
        entries = leader[i - 1 :]
        prev_index = i - 1
        if prev_index == 0:
            # Rewrite the whole log, which should always succeed.
            prev_term = 0
        else:
            prev_term = leader[prev_index - 1].term
        success = append_entries(follower, prev_index, prev_term, entries)
        assert success == expected_success
        if success and first_succeeded_at is None:
            first_succeeded_at = i
        if success:
            assert follower == leader
        else:
            assert follower != leader
    assert first_succeeded_at is not None
    assert first_succeeded_at == expected_index
