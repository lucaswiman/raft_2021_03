import argparse
import socket
import sys
import threading
from typing import *

"""
A critical feature of these functions is that they work with messages
as an "indivisible" unit.  A message is assumed to be an arbitrary
array of bytes.  When sent, the entire message is sent as one
unit.  When received, the entire message is returned exactly as it was
sent.  This behavior is a bit different than a normal network socket
where `send()` and `recv()` operations often introduce fragmentation
and return partial data.

To solve this problem, you should have your functions work with
size-prefixed data.  That is, all low-level I/O should embed a size
field that indicates how many bytes of data comprise the message.
Functions such as `recv_message()` should use the size to know exactly
how big the message is when it's received.
"""

def send_message(sock: socket.socket, msg: bytes):
    """
    A message is an arbitrary bytestring.
    
    When sent, it should include a size prefix of how long the string is,
    followed by an ASCII `:` character (data afterwards can be arbitrary binary data).
    The size prefix consists of one or more ASCII digits.
    """
    encoded_msg = b"%s:%s" % (str(len(msg)).encode(), msg)
    sock.send(encoded_msg)


def recv_message(sock: socket.socket) -> Optional[bytes]:
    """
    Reads a message off the socket. Returns None if the socket has been disconnected.
    """
    size_chars = ''
    while True:
        char = sock.recv(1)
        if char == b'':
            # Disconnection
            return None
        if char.isdigit():
            size_chars += char.decode('ascii')
        elif char == b":":
            break
        else:
            raise ValueError(f'Invalid character for size prefix: {char=}')
    size = int(size_chars)
    return sock.recv(size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="recv serves and prints to screen; send reads from stdin.")
    parser.add_argument("command", nargs=1, help="recv|send")
    parser.add_argument("--port", type=int, help="Port to open a socket on.", default=18_000)
    args = parser.parse_args()
    [command] = args.command
    port = args.port
    if command == "recv":
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
            sock.bind(("", port))
            sock.listen(1)
            client, addr = sock.accept()
            while True:
                msg = recv_message(client)
                if msg is None:
                    print("Connection closed; reinitializing socket.")
                    sock.close()
                    break
                else:
                    print(f"Received message: {msg=}")
    elif command == "send":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', port))
        send_message(sock, sys.stdin.buffer.read())
        sock.close()
    else:
        raise ValueError(f"Invalid command: {command}")
