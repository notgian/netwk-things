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

        print(f"Client name: {client_name}")
        print(f"Server name: {res["server_name"]} \n")

        print(f"Client number: {number}")
        print(f"Server number: {res["number"]}")
        print(f"Sum: {number + res["number"]} \n")

        
        clientSocket.close()

if __name__ == "__main__":
    main()
