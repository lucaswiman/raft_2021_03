from typing import NamedTuple, Any, List, Optional

ItemType = Any  # or Dict[str, Any] or Tuple[str, Any]?

# Each log entry consists of a term number and an item
class LogEntry(NamedTuple):
    term: int
    item: ItemType


Log = List[LogEntry]


# Implementation of "AppendEntries"
def append_entries(log: Log, prev_index: int, prev_term: int, entries: List[ItemType]) -> bool:
    """
    Note that indexes are 1-based, as in the paper.
    
    When appending at the beginning of the log, use prev_index=0, and prev_term is ignored.
    """
    if prev_index != 0:
        if len(log) < prev_index:
            # No holes.
            return False
        prev_entry = log[prev_index - 1]
        if prev_entry.term != prev_term:
            # Previous term must match.
            return False
    if any(entry.term < prev_term for entry in entries):
        # Terms should be non-decreasing.
        return False
    for entry, next_entry in zip(entries, entries[1:]):
        if entry.term > next_entry.term:
            # Terms should be non-decreasing.
            return False
    # At this point, the preconditions have been satisfied, and we are going
    # to write the entries to the log.
    extant_entries = entries[prev_index:prev_index + len(entries)]
    if extant_entries != entries:
        # See (3) from figure 2 ("Receiver implementation") in the raft paper.
        del log[prev_index:]
    log[prev_index:prev_index+len(entries)] = entries
        
    return True
