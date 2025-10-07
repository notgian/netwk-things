"""
========================================================
CSNETWK: Group #5
Section: S13

File: server(extra).py
Laboratory #3: Introduction to Sockets Programming

Description:
------------
This file implements the concurrent server program. It:
- Listens on port 4025 and accepts client connections.
- Uses threading (_thread.start_new_thread) so multiple clients can
  be handled simultaneously without blocking each other.
- Receives the client’s name and number, validates the number, and
  generates its own random integer.
- Displays the client’s name, server’s name, both numbers, and their sum.
- Sends back a message containing the server’s name and number.
- Terminates gracefully if an out-of-range value is received.

Connection:
-----------
Works with client.py, which sends the client’s name and number.
This file extends the single-client server (server.py) by supporting
multiple clients at once through concurrent threading.
========================================================
"""

from socket import *
from pickle import dumps, loads
from random import randint
from _thread import start_new_thread

server_name = "Baby Oil Pealike"

def handle_client(c):
    try:
        message_recv = loads(c.recv(1024))

        if not message_recv:  # no data, client disconnected
            return

        if message_recv["number"] < 1 or message_recv["number"] > 100:
            print("Received a number out of range, terminating server!")
            return

        print(f"Client name: {message_recv['client_name']}")
        print(f"Server name: {server_name} \n")

        random_num = randint(1, 100)

        print(f"Client number: {message_recv['number']}")
        print(f"Server number: {random_num}")
        print(f"Sum: {message_recv['number'] + random_num} \n")

        message_send = {"server_name": server_name, "number": random_num}

        c.send(dumps(message_send))

    finally:
        print(f"-------------------------------------------")
        c.close()

def main():
    host = ''
    port = 4025
    serverSocket = socket(family=AF_INET, type=SOCK_STREAM)
    serverSocket.bind((host, port))
    serverSocket.listen(5)

    print(f"Server of {server_name} listening on port {port}")

    while True:
        connectionSocket, addr = serverSocket.accept()
        start_new_thread(handle_client, (connectionSocket,))

if __name__ == "__main__":
    main()

