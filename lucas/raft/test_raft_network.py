from raft_network import MockNetwork


def test_send_receive():
    network = MockNetwork(5)
    node1 = network.create_node(1)
    node2 = network.create_node(2)
    node1.send(2, b"foo")
    message = node2.receive()
    assert message == b"foo"
    network.disable(1)
    node2.send(1, b"bar")
    assert node1.receive() is None
    network.enable(1)
    node2.send(1, b"bar")
    assert node1.receive() == b"bar"


def test_random():
    import random

    random.seed(0)
    network = MockNetwork(5)
    node1 = network.create_node(1)
    node2 = network.create_node(2)
    network.message_failure_rate = 0.25
    for _ in range(1000):
        node1.send(2, b"")
    failed = 0
    for _ in range(1000):
        if node2.receive() is None:
            failed += 1
    assert 200 < failed < 300
