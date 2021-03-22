import argparse
import socket
import sys
import threading
import re
from typing import *
import transport


DATA = {}


def process_command(sock: socket.socket):
    """
    Commands have the form:
        set:key=value
        get:key
    
    key much match the regular expression \w+
    """
    command = transport.recv_message(sock)
    print(f"Receieved {command=}")
    if command.startswith(b'set:'):
        [(key, value)] = re.findall(rb"set:(\w+)=(.*)", command)
        DATA[key.decode('ascii')] = value
        transport.send_message(sock, b"Executed command")
    elif command.startswith(b'get:'):
        [key] = re.findall(rb"get:(\w+)", command)
        key = key.decode('ascii')
        if key in DATA:
            transport.send_message(sock, DATA[key])
        else:
            transport.send_message(sock, (f"Key {key} not found.").encode('utf-8'))
    elif command.startswith(b'delete:'):
        [key] = re.findall(rb"delete:(\w+)", command)
        key = key.decode('ascii')
        if key in DATA:
            del DATA[key]
            transport.send_message(sock, (f"Deleted key {key}.").encode('utf-8'))
        else:
            transport.send_message(sock, (f"Key {key} not found.").encode('utf-8'))
    else:
        raise ValueError(f'Invalid command: {command}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Serves the key-value store.")
    parser.add_argument("--port", type=int, help="Port to open a socket on.", default=18_000)
    args = parser.parse_args()
    port = args.port
    
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        sock.bind(("", port))
        sock.listen(1)
        client, addr = sock.accept()
        while True:
            msg = process_command(client)
            if msg is None:
                print("Connection closed; reinitializing socket.")
                sock.close()
                break
            else:
                print(f"Received message: {msg=}")
