import messages
from config import ACK_TIMEOUT
from time import sleep
from threading import Thread

class ReliabilityLayer():
    """ The reliability is responsible for handling ack messages.

        Disconnect callback is what is called when a peer disconnects.
        It should have one arg, being the address of the peer that
        disconnected.

    """
    def __init__(self, on_disconnect):
        # connections is a dict with each address, mapped to a dict.
        # Example: 
        # self.connections["192.168.1.21:1234"] = {
        #   "sequence" : 1
        # }
        self.connections = dict()

        # each member is a dict {"address": addr, "ack_number": number}
        # each member is assumed to be correct
        # a list of the acks to resolve.
        self.ack_resolution_list = list()
        self.processing_acks = False
        self.disconnect_callback = on_disconnect
        # hold a dict of connections and their current sequence numbers

        self.ack_resolution_thread = Thread(target=self.__process_ack_resolution__, daemon=True)

    def handle_ack(self, address: tuple, ack_number: int):
        """ Call this on handling an ack on the client.
            This takes the source address of the ack and the actual
            ack number. And appends this ack to the ack_resolution_list to be
            processed.
        """
        self.ack_resolution_list.append({
            "address": address,
            "ack_number": ack_number
        })

    def get_sequence(self, address: str):
        """ Gets the sequence number for a message that will be sent.
            In the case no message has been sent by this address yet,
            it will initialize its sequence number to 1.
        """
        if address not in self.connections:
            self.connections[address] = {"sequence": 1}

        return self.connections[address]["sequence"]

    def await_ack(self, address: str):
        """ Call this upon sending a message in the game protocol handler
            Waits thrice with a timeout/interval defined in the config.py
            file. Once at the end of this, no ack has been received, the client
            corresponding to the given address will be marked as disconnected.

            Returns True if the ack message was received and the connection
            persists. Otherwise, return false if the ack message was not received
            after three retries, with an interval of the ACK_TIMEOUT, the
            connection is logically considered terminated.
        """
        if address not in self.connections:
            self.connections[address] = {"sequence": 1}

        attempt_number = 1
        current_sequence = self.connections[address]["sequence"]

        sleep(ACK_TIMEOUT)
        while attempt_number <= 3:
            if self.connections[address]["sequence"] > current_sequence:
                return True

            attempt_number += 1
            sleep(ACK_TIMEOUT)
        self.disconnect_callback(address)
        return False

    def start(self):
        """ Starts the thread to process acks """
        if self.processing_acks:
            print("[WARN] Already processing acks!")
            return

        self.process_acks = True
        self.ack_resolution_thread.start()

    def stop(self):
        """ Stops the thread to process acks """
        if not self.process_acks:
            return
        self.process_acks = False

    def __process_ack_resolution__(self):
        """ A persistent thread that begins running on the creation of the
            reliability layer. Processes the acks in the ack_resolution_list and
            marks these acks as having been received

            Yes, I'm aware of the overhead, but eh just let it be.
        """
        while self.process_acks:
            sleep(ACK_TIMEOUT/4)  # sleep a little to not be overwhelming zzz
            if len(self.ack_resolution_list) == 0:
                continue
            for i, ack in enumerate(self.ack_resolution_list):
                address = ack["address"]
                ack_number = ack["ack_number"]
                if self.connections[address]["sequence"] + 1 == ack_number:
                    self.connections[address]["sequence"] += 1
                    self.ack_resolution_list.pop(i)
                    break
                    # break is necessary bc a member of the queue is popped,
                    # changing consequent indices


# Message is sent from the client, and the await_ack with their local_ip is
# passed to await_ack