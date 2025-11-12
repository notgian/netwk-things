import socket
import random

# name = socket.gethostname()
# ip = socket.gethostbyname(name)
# print(name, ip)

DEFAULT_PORT = 4566


class Client:
    def __init__(self, port=DEFAULT_PORT):

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as e:
            print(f"Failed to create socket: {e}")
            exit()

        self.opponent_addr = None

        # automatically get host info
        name = socket.gethostname()
        ip = socket.gethostbyname(name)

        self.hostname = ip
        self.host = ip
        self.port = port

        self.buffer_size = 4096

        self.match_data = dict()

        print("Initialized client!")
        print("Name : " + self.hostname)
        print("IP: " + self.host)

    def start_hosting(self):
        """ Acts as the Host Peer."""
        try:
            self.sock.bind((self.host, self.port))
            print (f"\n[Host] Listening on {self.host}:{self.port}")
        except socket.error as e:
            print(f"\n[Host]  Failed to bind socket {e}")
            return False

        try:
            print("[Host] Waiting for a connection...")
            data, address = self.sock.recvfrom(self.buffer_size)
            message = data.decode("utf-8")
            print(f"\n[Host] Received message from {address}:")
            print(message)

            if "message_type: HANDSHAKE_REQUEST" in message:
                print("\n[HANDSHAKE_REQUEST] Received HANDSHAKE_REQUEST")
                self.opponent_addr = address
                seed = random.randint(1,99999)
                self.match_data['seed'] = seed

                response_message = (
                    f"message_type: HANDSHAKE_RESPONSE\n"
                    f"seed: {seed}\n"
                )

                self.sock.sendto(response_message.encode('utf-8'), self.opponent_addr)
                print("[HANDSHAKE_RESPONSE] Sent HANDSHAKE_RESPONSE")
                return True
            else:
                print("\n[HANDSHAKE_REQUEST] Received non-handshake message. Ignoring")
                return False

        except socket.error as e:
            print(f"\n[Host] Socket error while hosting: {e}")
            return False

    def join_host(self, host, port):
        host_addr = (host, port)

        request_message = f"message_type: HANDSHAKE_REQUEST\n"

        try:
            print(f"\n[CLIENT] Joining {host}:{port}")
            self.sock.sendto(request_message.encode('utf-8'), host_addr)

            self.sock.settimeout(5.0)

            data, address = self.sock.recvfrom(self.buffer_size)
            message = data.decode("utf-8")

            self.opponent_addr = address

            print(f"\n[CLIENT] Received message from {address}:")
            print(message)

            if "message_type: HANDSHAKE_RESPONSE" in message:
                print("[HANDSHAKE_REQUEST] Received correct message. Handshake successful")

                for line in message.split('\n'):
                    if 'seed:' in line:
                        self.match_data['seed'] = int(line.split(':')[1].strip())
                        print(f"Received seed: {self.match_data['seed']}")
                return True
            else:
                print("\n[HANDSHAKE_REQUEST] Received non-handshake message. Ignoring")
                return False

        except socket.timeout:
            print("\n[CLIENT] Socket timed out. Ignoring")
            self.opponent_addr = None
            return False
        except socket.error as e:
            print(f"\n[CLIENT] Socket error while joining: {e}")
            self.opponent_addr = None
            return False

    def send_message(self, message_data):
        if not self.opponent_addr:
            print("\n[MESSAGE] Not connected to any peer. Host or join a game first")
            return

        try:
            self.sock.sendto(message_data.encode('utf-8'), self.opponent_addr)
        except socket.error as e:
            print(f"\n[MESSAGE] Error while sending message: {e}")

