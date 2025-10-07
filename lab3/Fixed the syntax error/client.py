"""
========================================================
CSNETWK: Group #5
Section: S13

File: client.py
Laboratory #3: Introduction to Sockets Programming

Description:
------------
This file implements the client program. It:
- Prompts the user for an integer input (1–100, or 999 to terminate server).
- Sends the client’s name and chosen number to the server.
- Receives the server’s name and generated number in return.
- Displays both names, both numbers, and their sum.
- Closes the connection after processing the response.

Connection:
-----------
Works with server.py (single-client) or server(extra).py (multi-client),
both listening on port 4025.
========================================================
"""


from socket import *
from pickle import dumps, loads

hostname = '127.0.0.1'  
port = 4025

clientSocket = socket(family=AF_INET, type=SOCK_STREAM)
clientSocket.connect((hostname, port))

client_name = "Wheezy Joe Vinaigrette"

def main():
    valid_input = False

    number = 0 

    while (not valid_input):
        inp = input("Please enter a number from 1 and 100: ")
        print("") # newline
        
        try:
            number = int(inp)

            if number < 1:
                print("Number is too small! Minimum number is 1!")
            elif number > 100 and number != 999: # 999 is the magic number to close the server
                print("Number is too big! Maximum number is 100!")
            else:
                valid_input = True

        except ValueError:
            print("Please enter a valid number!")
        
    message = {"client_name": client_name, "number": number}
    clientSocket.send(dumps(message))

    if number != 999:
        res = loads(clientSocket.recv(1024))

        #Display results
        print(f"Client name: {client_name}")
        print(f"Server name: {res['server_name']} \n")

        print(f"Client number: {number}")
        print(f"Server number: {res['number']}")
        print(f"Sum: {number + res['number']} \n")

        
        clientSocket.close()

if __name__ == "__main__":
    main()
