import transport
import concurrent.futures

# with concurrent.futures.ThreadPoolExecutor() as executor:
#     future = executor.submit(foo, 'world!')
#     return_value = future.result()
#     print(return_value)

def echo_test(sock_server, sock_client):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for n in range(0, 8):
            print(f"Testing {10 ** n}.")
            msg = b'x'*(10**n)         # 1, 10, 100, 1000, 10000, bytes etc...
            transport.send_message(sock_client, msg)
            future = executor.submit(transport.recv_message, sock_server)
            # response = transport.recv_message(sock_server)
            breakpoint()
            assert msg == response

def main(port):
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.bind(("", port))  # blocks here? TODO.
    sock.listen(1)
    sock_server, addr = sock.accept()
    
    sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_client.connect(('localhost', port))
    
    echo_test(sock_server, sock_client)
    sock_server.close()
    sock_client.close()

if __name__ == "__main__":
    main(15_000)
