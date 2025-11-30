import socket
import config

class Client:
    """Handles the low-level UDP socket operations (Sending/receiving bytes)."""
    def __init__(self, buffer_size=config.BUFFER_SIZE):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error as e:
            print(f"[Client] Failed to create socket: {e}")
            exit()

        self.buffer_size = buffer_size

        print("Initialized client!")

    def bind_socket(self, host, port):
        """ Binds the socket so that the Host is online"""
        try:
            self.sock.bind((host, port))
            print (f"\nSocket bound to {host}:{port}")
            return True
        except socket.error as e:
            print(f"\nFailed to bind socket {host}:{port}. Error: {e}")
            return False

    def send_to(self, message_text: str, address: tuple):
        """Encodes and sends a plain text message to the given address."""
        try:
            self.sock.sendto(message_text.encode(), address)
        except socket.error as e:
            print(f"\nFailed to send message to {address}. Error: {e}")

    def receive_from(self, timeout=None):
        """
        Receive a plain text message from the given address.
        Returns the decoded message (str) and the sender's address, None if no message is received.
        """
        try:
            self.sock.settimeout(timeout)
            data, address = self.sock.recvfrom(self.buffer_size)
            message = data.decode('utf-8')
            return message, address
        except socket.timeout:
            return None, None
        except socket.error as e:
            print(f"\nSocket error on receive. Error: {e}")
            return None, None
        finally:
            self.sock.settimeout(None)

    def close(self):
        """Close the socket connection."""
        self.sock.close()
        print("\nSocket closed!")