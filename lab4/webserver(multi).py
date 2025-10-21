# -*- coding: utf-8 -*-
"""WebServer.py - Single and Multithreaded HTTP Server"""

from socket import *
import sys
import threading

# ----------------------------
# Configuration
# ----------------------------
serverPort = 6789
MULTITHREAD = True  # Set to False for single-threaded mode

# Create a TCP socket
serverSocket = socket(AF_INET, SOCK_STREAM)

# Bind the socket to the port
serverSocket.bind(('', serverPort))

# Start listening (max queued connections = 5)
serverSocket.listen(5)

print(f"Server running on port {serverPort} (Multithreaded = {MULTITHREAD})")


# ----------------------------
# Handle a client request
# ----------------------------
def handle_client(connectionSocket, addr):
    try:
        # Receive the request message from the client
        message = connectionSocket.recv(1024).decode()

        if not message:
            connectionSocket.close()
            return

        # Parse the requested file name
        filename = message.split()[1]
        f = open(filename[1:])  # remove leading '/'
        outputdata = f.read()

        # Send HTTP header line
        connectionSocket.send("HTTP/1.1 200 OK\r\n\r\n".encode())

        # Send file contents
        for i in range(0, len(outputdata)):
            connectionSocket.send(outputdata[i].encode())

        connectionSocket.send("\r\n".encode())

    except IOError:
        # File not found, send 404 response
        connectionSocket.send("HTTP/1.1 404 Not Found\r\n\r\n".encode())
        connectionSocket.send(
            "<html><body><h1>404 Not Found</h1></body></html>\r\n".encode()
        )
    except Exception as e:
        print(f"Error handling client {addr}: {e}")
    finally:
        # Close the client socket
        connectionSocket.close()


# ----------------------------
# Main Server Loop
# ----------------------------
while True:
    print("Ready to serve...")
    connectionSocket, addr = serverSocket.accept()
    print(f"Connection from {addr}")

    if MULTITHREAD:
        # Multithreaded mode: spawn a new thread for each client
        client_thread = threading.Thread(target=handle_client, args=(connectionSocket, addr))
        client_thread.start()
    else:
        # Single-threaded mode: handle client directly
        handle_client(connectionSocket, addr)


# Close the server socket
serverSocket.close()
sys.exit()