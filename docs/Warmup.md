# Introduction to Messages and Concurrency

To implement Raft, you minimally need to be able to write
programs that exchange network messages.  In addition, you
will need to write programs with concurrency in the form
of threads (or some other alternative).   This exercise
takes you through a few of the basic elements of this.
Python is shown, but most of this can be adapted to other
languages as well.

## Part 1:  Sockets

The most low-level way to communiate on the network is to write
code using sockets.

A socket represents an end-point for communicating on the network.
Think of it as being similar to a file. With a file, you use the
`open()` function to create a file object and then you use `read()`
and `write()` methods to process data.  A socket is a similar idea.

To create a socket, use the `socket` library.  For example:

```
from socket import socket, AF_INET, SOCK_STREAM
sock = socket(AF_INET, SOCK_STREAM)
```

The `AF_INET` option specifies that you are using the internet
(version 4) and the `SOCK_STREAM` specifies that you want a reliable
data stream.  In technical terms, this socket will be used for
TCP/IPv4 communication.  Change the `AF_INET` to `AF_INET6` if you
want to use TCP/IPv6.

### Making a Connection

Further use of a socket depends on the program's role in the
communication.  If a program is going to wait and listen for incoming
connections, it is known as a server.  If a program makes an outgoing
connection, it is a client.  The client case is simpler so let's start
with that.  Here's an example of using a socket to make an outgoing
HTTP request and reading the response:

```
sock = socket(AF_INET, SOCK_STREAM)
sock.connect(('www.python.org', 80))
sock.send(b'GET /index.html HTTP/1.0\r\n\r\n')
parts = []
while True:
    part = sock.recv(1000)     # Receive up to 1000 bytes (might be less)
    if not part:
        break                  # Connection closed
    parts.append(part)
# Form the complete response
response = b''.join(parts)
print("Response:", response)
```

Try running the above program.  You'll probably get a response
indicating some kind of error.  That is fine. Our goal is not to
implement HTTP, but simply to see some communication.

Now, a few important details.

1. Network addresses are specified as a tuple `(hostname, port)` where
`port` is a number in the range 0-65535.

2. The port number must be known in advance.  This is usually dictated
by a standard. For example, port 25 is used for email, port 80 is used
for HTTP, and port 443 is used for HTTPS.  See
https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml

3. Data is sent using `sock.send()`.  Data is received `sock.recv()`.
Both of these operations only work with byte-strings.  If you are
working with text (Unicode), you will need to make sure it's properly
encoded/decoded from bytes.

4. Data is received and transmitted in fragments.  The `sock.recv()`
accepts a maximum number of bytes, but that it is only a maximum.  The
actual number of bytes returned might be much less. It is your
responsibility to reassemble data from fragments into a complete
response.  Thus, you might have to collect parts and put them back
together as shown.  A closed connection or "end of file" is indicated
by `sock.recv()` returning an empty byte string.

### Receiving Connections

Receiving connections on a socket is a bit more complicated.  Recall
that clients (above) need to know the address and port number in order
to make a connection.  To receive a connection, a program first needs
to bind a socket to a port.  Here's how you do that:

```
sock = socket(AF_INET, SOCK_STREAM)
sock.bind(('', 12345))         # Bind to port 12345 on this machine
sock.listen()                  # Enable incoming connections
```

To accept a connection, use the `sock.accept()` method:

```
client, addr = sock.accept()     # Wait for a connection
```

`accept()` returns two values.  The first is a completely new socket
object that represents the connection back to the client.  The second
is the remote address `(host, port)` of the client.  You use the
`client` socket for further communication.  Use the address `addr` for
diagnostics and to do things like reject connections from unknown
locations.

One confusion with servers concerns the initial socket that you create
(`sock`).  The initial socket really only serves as a connection point
for clients. Think of it like the phone number for a large organization.
You call the central number.  A voicemail menu asks you who you're trying
to reach and then you're connected to a different line.  It's the same
general idea here.  All further communication will use the `client` socket
returned by `sock.accept()`.

Here is an example of a server that reports the current time back to
clients:

```
import time
from socket import socket, AF_INET, SOCK_STREAM

sock = socket(AF_INET, SOCK_STREAM)
sock.bind(('',12345))
sock.listen()
while True:
    client, addr = sock.accept()
    print('Connection from', addr)
    msg = time.ctime()    # Get current time
    client.sendall(msg.encode('utf-8'))
    client.close()
```

Try running this program on your machine.  While it is running, try
connecting to it from a separate program.

```
from socket import socket, AF_INET, SOCK_STREAM

sock = socket(AF_INET, SOCK_STREAM)
sock.connect(('localhost', 12345))
msg = sock.recv(1000)              # Get the time
print('Current time is:', msg.decode('utf-8'))
```

Run this program (separately from the server).  You should see it
print the current time.

### Exercise

Modify the time program above to operate as an echo server.  An echo
server reads data from the client and echos it back.  For
example, here's a client you can use to experiment:

```
from socket import socket, AF_INET, SOCK_STREAM

def main(addr):
    sock = socket(AF_INET, SOCK_STREAM)
    sock.connect(addr))
    msg = input("Say >")
    sock.sendall(msg.encode('utf-8'))
    response = sock.recv(len(msg))
    print("Received >", response)

main(('localhost', 12345))
```

## Part 2: Message Passing

To make messaging more sane, it is sometimes common to use
size-prefixed messages.  This is a technique where every message is
prepended with a byte-count to indicate how large the message is.
Here is some sample code that sends a size-prefixed message:

```
def send_message(sock, msg):
    size = b'%10d' % len(msg)    # Make a 10-byte length field
    sock.sendall(size)
    sock.sendall(msg)
```

Write the corresponding `recv_message(sock)` function.  This function
should read the size, then read exactly that many bytes to return the
exact message that was sent.

When you are done, rewrite your echo server and client to use
`send_message()` and `recv_message()`.

## Part 3 - Concurrency

Sometimes a program needs to do more than one thing at a time.  To do that,
you might use threads.  Here is a simple Python example:

```
import time
import threading

def countdown(n):
    while n > 0:
        print('T-minus', n)
	time.sleep(1)
	n -= 1

def countup(stop):
    x = 0
    while x < stop:
        print('Up we go', x)
	time.sleep(1)
	x += 1

def main():
    t1 = threading.Thread(target=countdown, args=[10])
    t2 = threading.Thread(target=countup, args=[5])
    t1.start()
    t2.start()
    print('Waiting')
    t1.join()
    t2.join()
    print('Goodbye')

main()
```

Run this program and watch what it does.  You should see the `countdown()`
and `countup()` functions running at the same time.

There's not much you can do with threads once created.  The `join()`
method is used if you want to wait for a thread to terminate.  There is
no way to kill a thread manually.

Sometimes it is useful for threads to communicate.  One way to do
that is to use a `Queue`.  For example:

```
import threading
import queue
import time

def producer(q):
    for i in range(10):
        print('Producing', i)
        q.put(i)
        time.sleep(1)
    q.put(None)
    print('Producer done')

def consumer(q):
    while True:
        item = q.get()
	if item is None:
	    break
	print('Consuming', item)
    print('Consumer goodbye')

def main():
    q = queue.Queue()
    t1 = threading.Thread(target=producer, args=[q])
    t2 = threading.Thread(target=consumer, args=[q])
    t1.start()
    t2.start()
    print('Waiting')
    t1.join()
    t2.jon()
    print('Done')

main()
```

Run this program and observe its behavior.  Make sure you understand what
is happening.

## Part 4 - Challenge

Take all of the parts of this warmup and implement a chat server and client.
The chat server should listen for incoming connections from any number
of clients.  Any message sent from a client should be echoed on all
of the other clients.   Hint: use threads and queues.






 
