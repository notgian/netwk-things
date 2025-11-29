import messages
from config import ACK_TIMEOUT
from time import sleep

class ReliabilityLayer():
    """ The reliability is responsible for handling ack messages.

        Disconnect callback is what is called when a peer disconnects.
        It should have one arg, being the address of the peer that
        disconnected.

    """
    def __init__(self, on_disconnect):
        # connections is a dict with each address, mapped to a dict.
        # Example: (btw never should localhost be passed in our program)
        # self.connections[127.0.0.1] = {
        #   "sequence" : 1
        # }
        self.connections = list()

        # "queue" is a misnomer bc each value here will be processed on every
        # each member is a dict {"address": addr, "ack_number": number}
        # each member is assumed to be correct
        self.ack_queue = list()
        self.processing_acks = False
        self.disconnect_callback = on_disconnect
        # hold a dict of connections and their current sequence numbers

    def handle_ack(self, address, ack_number):
        """ Call this on handling an ack on the client.
            This takes the address of the
        """
        pass

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
            if self.connections[address]["sequence"] <= current_sequence:
                return True

            attempt_number += 1
            sleep(ACK_TIMEOUT)
        self.disconnect_callback(address)
        return False

    def __process_acks__(self):
        """ A persistent thread that begins running on the creation of the
            reliability layer. Processes the acks in the ack_queue and
            marks these acks as having been received

            Yes, I'm aware of the overhead, but eh just let it be.
        """
        self.process_acks = True
        while self.process_acks:
            sleep(ACK_TIMEOUT/3)
            if len(self.ack_queue) == 0:
                continue
            for i, ack in enumerate(self.ack_queue):
                address = ack["address"]
                ack_number = ack["ack_number"]
                if self.connections[address]["sequence"]+1 == ack_number:
                    self.connections[address]["sequence"] += 1
                    self.ack_queue.pop(i)
                    break
                    # break is necessary bc a member of the queue is popped,
                    # changing consequent indices


# Message is sent from the client, and the await_ack with their local_ip is
# passed to await_ack


