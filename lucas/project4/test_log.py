from log import LogEntry, append_entries

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

def test_append_empty():
    orig_log = [
        LogEntry(1, "x"),
        LogEntry(1, "y"),
        LogEntry(2, "z"),
    ]
    log = list(orig_log)
    assert append_entries(log=log, prev_index=0, prev_term=0, entries=[])
    assert log == orig_log
    assert append_entries(log=log, prev_index=1, prev_term=1, entries=[])
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
