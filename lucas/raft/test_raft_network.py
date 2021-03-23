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
