"""
========================================================
CSNETWK: Group #5
Section: S13

File: server.py
Laboratory #3: Introduction to Sockets Programming

Description:
------------
This file implements the single-client server program. It:
- Listens on port 4025 and accepts one client connection at a time.
- Receives the client’s name and number, validates the number, and
  generates its own random integer.
- Displays the client’s name, server’s name, both numbers, and their sum.
- Sends back a message containing the server’s name and number.
- Closes the connection after serving each client.
- Terminates gracefully if an out-of-range value is received.

Connection:
-----------
Works with client.py, which sends the client’s name and number.
Unlike server(extra).py, this version only handles one client at a time.
========================================================
"""

from socket import *
from pickle import dumps, loads
from random import randint

port = 4025
server_name = "Baby Oil Pealike"

serverSocket = socket(family=AF_INET, type=SOCK_STREAM)
serverSocket.bind(('', port))
serverSocket.listen(1)

print(f"Server of {server_name} listening on port {port}")

while True:
    connectionSocket, addr = serverSocket.accept()

    message_recv = loads(connectionSocket.recv(1024))

    if message_recv["number"] < 1 or message_recv["number"] > 100:
        print("Received a number out of range, terminating server!")
        connectionSocket.close()
        break

    print(f"Client name: {message_recv['client_name']}")
    print(f"Server name: {server_name} \n")

    random_num = randint(1, 100) 

    print(f"Client number: {message_recv['number']}")
    print(f"Server number: {random_num}")
    print(f"Sum: {message_recv['number'] + random_num} \n")

    message_send = {"server_name": server_name, "number": random_num}

    connectionSocket.send(dumps(message_send))
    connectionSocket.close()
