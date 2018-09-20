from threading import Timer

count = 0

class InfiniteTimer():
    """A Timer class that does not stop, unless you want it to."""

    def __init__(self, seconds, target, args):
        self._should_continue = False
        self.is_running = False
        self.seconds = seconds
        self.target = target
        self.thread = None
        self.args = args

    def _handle_target(self, args):
        self.is_running = True
        self.target(args)
        self.is_running = False
        self._start_timer()

    def _start_timer(self):
        if self._should_continue: # Code could have been running when cancel was called.
            self.thread = Timer(self.seconds, self._handle_target, self.args)
            self.thread.start()

    def start(self):
        if not self._should_continue and not self.is_running:
            self._should_continue = True
            self._start_timer()
        else:
            print("Timer already started or running, please wait if you're restarting.")

    def cancel(self):
        if self.thread is not None:
            self._should_continue = False # Just in case thread is running and cancel fails.
            self.thread.cancel()
        else:
            print("Timer never started or failed to initialize.")

def func(add):
    global count
    count += add
    print(count)

def main():

    print("Starting...")
    timer_task = InfiniteTimer(0.5, func, [2])
    timer_task.start()

if __name__ == '__main__':
    main()
