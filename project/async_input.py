from threading import Thread

class AsyncInput:
    """ A class that provides a simple way to asychronously take user
        input in a none-blocking way

        intermediate_callback is an optional argument: a function that
        the input thread runs the input through on each input. It
        attempts to process the input using a certain criteria (i.e. it
        starting with a specific prefix). It expects a return value of a
        boolean. True indicates that the intermediate function was able
        to process the input for something and does not push the input
        to the buffer anymore. Otherwise, if false, it will push the
        input into the buffer as it does normally.
    """
    def __init__(self, intermediate_callback=False):
        self.taking_input = False
        self.input_thread = Thread(target=self.__take_input__, args=(intermediate_callback,), daemon=True)
        self.input_buff = ""

    def flush(self):
        """ Flushes the input buffer by setting it back to an empty string """
        self.input_buff = ""

    def awaitInput(self, message=""):
        """ Waits for input and returns the input received. Take note that this
            is a blocking job, and will not proceed until input has been
            received. Causes the input buffer to be flused.
            IMPORTANT: Does not return empty inputs!
            If the input thread is not already running, this returns None.
        """
        if not self.taking_input:
            print("[ERROR] Cannot await input because input thread is not running!")
            return None
        self.flush()
        print(message)
        while self.input_buff == "":
            pass

        buff_content =  self.input_buff
        self.flush()
        return buff_content

    def getInput(self):
        """ Gets the content of the input buffer and returns this. Note
            that this can cause it to return an empty string. This is intended.
            Unlike await input, this is not a blocking job. Flushes the input
            buffer, but also doesn't care whether the input thread is started 
            or not.
        """
        buff_content =  self.input_buff
        self.flush()
        return buff_content

    def start(self):
        """ Starts the input thread. """
        if self.taking_input:
            print("[WARN] Already taking input!")
            return

        self.taking_input = True
        self.input_thread.start()

    def stop(self):
        """ Stops the input thread. Take note, however, that this cannot
            terminate the actual input function that is run, so the user
            still has to press enter to actually exit the input() function.
        """
        if not self.taking_input:
            print("[WARN] Already not taking input!")
            return

        self.taking_input = False

    def __take_input__(self, intermediate_callback=None):
        """ The function that is run by the thread. Do not run this
            separately
        """
        print("STARTED")
        while self.taking_input:
            inp = input().strip()
            if intermediate_callback is not None:
                res = intermediate_callback(inp)
                self.input_buff = "" if res else inp
            else:
                self.input_buff = inp
        print("ENDED")
