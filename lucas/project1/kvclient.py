import argparse
import socket
import sys
import threading
import re
from typing import *
import transport


DATA = {}


def process_command(sock: socket.socket, command, key, value=None):
    """
    Commands have the form:
        set:key=value
        get:key
    
    key much match the regular expression \w+
    """
    if command == "get":
        transport.send_message(sock, b"get:%s" % key.encode('ascii'))
        result = transport.recv_message(sock)
    elif command == "set":
        transport.send_message(sock, b"set:%s=%s" % (key.encode('ascii'), value.encode('ascii')))
        result = transport.recv_message(sock)
    else:
        raise ValueError(f"Invalid command {command=}")
    print(result.decode('utf-8'))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serves the key-value store.")
    parser.add_argument("--port", type=int, help="Port to open a socket on.", default=18_000)
    parser.add_argument("command", nargs=1, help="get|set")
    parser.add_argument("--key", type=str)
    parser.add_argument("--value", type=str, default=None)
    args = parser.parse_args()
    [command] = args.command
    port = args.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(('localhost', port))
    process_command(sock, command, args.key, args.value)
    sock.close()
