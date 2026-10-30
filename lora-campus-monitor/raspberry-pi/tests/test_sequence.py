from app.protocol import FLAG_BOOT
from app.sequence import NodeSequenceState, SequenceStatus, accept, classify


def state(seq, uptime):
    return NodeSequenceState(seq, uptime)


def test_first_packet():
    assert classify(NodeSequenceState(), 5, 300, 0).status is SequenceStatus.FIRST


def test_consecutive():
    r = classify(state(5, 300), 6, 360, 0)
    assert r.status is SequenceStatus.OK and r.lost == 0


def test_gap_counts_lost():
    r = classify(state(5, 300), 9, 540, 0)
    assert r.status is SequenceStatus.GAP and r.lost == 3


def test_duplicate():
    assert classify(state(5, 300), 5, 300, 0).status is SequenceStatus.DUPLICATE


def test_reboot_by_flag():
    r = classify(state(500, 30000), 0, 12, FLAG_BOOT)
    assert r.status is SequenceStatus.NODE_RESET and r.lost == 0


def test_reboot_missed_boot_packet():
    r = classify(state(500, 30000), 2, 130, 0)
    assert r.status is SequenceStatus.NODE_RESET and r.lost == 2


def test_accept_updates_state():
    s = NodeSequenceState()
    accept(s, 3, 200)
    assert (s.last_sequence, s.last_uptime) == (3, 200)
