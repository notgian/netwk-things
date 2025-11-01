import socket

# name = socket.gethostname()
# ip = socket.gethostbyname(name)
# print(name, ip)

DEFAULT_PORT = 4566


class Client:
    def __init__(self, port=DEFAULT_PORT):
        # automatically get host info
        name = socket.gethostname()
        ip = socket.gethostbyname(name)

        self.hostname = ip
        self.host = ip
        self.port = port

        self.match_data = dict()

        print("Initialized client!")
        print("Name : " + self.hostname)
        print("IP: " + self.host)

    def start_hosting():
        pass
        # create a UDP socket and listen for a HANDSHAKE_REQUEST

    def join_host(host, port):
        pass

    def send_message(message_data):
        pass
