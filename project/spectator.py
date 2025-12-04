import messages as m
from client import Client
from protocol import GameProtocolHandler
from config import HANDSHAKE_TIMEOUT
from threading import Thread

class Spectator:
    def __init__(self, host_ip, host_port, local_ip, local_port=0):
        self.net_client = Client()

        if not self.net_client.bind_socket(local_ip, local_port):
            exit()

        self.protocol = None
        self.local_addr = self.net_client.sock.getsockname()
        self.host_ip = (host_ip, host_port)

        self.is_listening = False
        self.listener_thread = Thread(target=self.__listen_loop__)
        self.is_taking_input = False
        self.input_thread = Thread(target=self.__user_input__)
        self.should_quit = False

        self.input_buff = ""
        print(f"Spectator client initialized. Will connect to {host_ip}:{host_port}")

    def connect_to_host(self):
        """ Connects to the host client by sending a HANDSHAKE_REQUEST message.
            Also waits for a corresponding HANDSHAKE_RESPONSE message and
            begins the initialization of the game.

            returns a boolean representing whether the connection was
            successful or not.
        """
        request_msg = m.SpectatorRequestMessage()

        try:
            print("\n[SPECTATOR] Connecting to HOST...")
            self.net_client.send_to(request_msg.as_text(), self.host_ip)

            message, address = self.net_client.receive_from(timeout=HANDSHAKE_TIMEOUT)

            if not message:
                print("\n[SPECTATOR] Connection timed out. Host not found")
                return False

            if address != self.host_ip:
                print("\n[SPECTATOR] Received response from unexpected address {address}.")
                return False

            self.protocol = GameProtocolHandler(self.net_client,
                                                self.local_addr,
                                                is_host=False,
                                                parent_user=None)
            message_dict = self.protocol._parse_message(message)

            # Handle handshake response here
            if message_dict.get('message_type') == m.MessageType.HANDSHAKE_RESPONSE.value:
                print("\n[SPECTATOR] Handshake successful!")

                seed = int(message_dict.get('seed', 0))
                match_data = {'seed': seed}
                print(f"[SPECTATOR] Received seed: {seed}")

                self.protocol.set_opponent(self.host_ip, match_data, is_host=False)
                # begin listening to prepare for battle setup
                self.__start_listening__()
                self.start_spectator_loop()
                return True
            else:
                print(f"\n[SPECTATOR] Received unexpected message response {message}.")
                return False
        except Exception as e:
            print(f"\n[SPECTATOR] Error during connection: {e}")
            return False

    # ===== Spectator Loop =====
    def start_spectator_loop(self):
        """Called after establishing a connection. Main loop: Listen for all battle m broadcasted by Host."""
        print("\n[SPECTATOR] Joined as Spectator. Now listening for battle messages")
        print("[SPECTATOR] Type chat messages freely.")
        print("[SPECTATOR] Type 'quit' or 'exit' to disconnect.\n")

        # Enable input thread (can be used for chat later)
        self.__start_taking_input__()

        # Keep main thread alive while listening
        while self.is_listening and not self.should_quit:
            pass

        self.cleanup()

    def cleanup(self):
        """Stops the thread that is listening for messages """
        print("[SPECTATOR] Disconnecting...")
        self.__stop_listening__()
        self.__stop_taking_input__()
        self.net_client.close()

    def __start_listening__(self):
        """ Starts a thread that loops, listening for  This is called
            after the handshake to allow for listening for all messages
            afterwhich. Also allows for seemingly synchronous (not really)
            handling of chat messages and game events.
        """

        if self.is_listening:
            print("[SPECTATOR] Already listening!")
            return
        self.listener_thread.start()
        self.is_listening = True

    def __stop_listening__(self):
        """ Stops the thread that is listening for messages """

        if not self.is_listening:
            print("[SPECTATOR] Already NOT listening!")
            return

        self.is_listening = False

    def __listen_loop__(self):
        """ Thread method: continously recives messages from the Host"""

        print(" ", flush=True)

        while self.is_listening:
            try:
                message, address = self.net_client.receive_from()

                if not message:
                    continue

                if address == self.host_ip:
                    print(f"\n[SPECTATOR RECEIVED]: \n{message}\n")
                    if self.protocol:
                        self.protocol.process_message(message, address)
                else:
                    print(f"\n[SPECTATOR] Received message from unexpected sender {address}.")
            except Exception as e:
                print(f"[SPECTATOR ERROR] Listener thread crash: {e}")
                break

    def __user_input__(self):
        """ Thread method: handles user input (only for chat) """
        while self.is_taking_input:
            try:
                inp = input().strip()

                if inp.lower() in ['quit', 'exit']:
                    self.should_quit = True
                    self.is_listening = False
                    self.is_taking_input = False
                    break

                if inp.startswith("/message "):
                    message = inp[len("/message "):].strip()
                    sender = self.fmt_address(self.local_addr)
                    self.protocol.send_chat_message(sender_name=sender, content_type=m.ChatMessageType.TEXT, content=message)
                elif inp and inp.startswith("/"):
                    print(f"[SPECTATOR] Command {inp.split()[0]} is not supported. Use /message.")

            except EOFError:
                break
            except Exception as e:
                break

    def __start_taking_input__(self):
        if self.is_taking_input:
            return
        self.is_taking_input = True
        self.input_thread.start()

    def __stop_taking_input__(self):
        if not self.is_taking_input:
            return
        self.is_taking_input = False

    def fmt_address(self, address = None) -> str:
        """ Helper method for address formatting. """
        if self.protocol:
            return self.protocol.fmt_address(address)
        if address is None:
            return "UNKNOWN"
        return f"{address[0]}:{address[1]}"