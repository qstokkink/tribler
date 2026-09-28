from asyncio import Event, Task, ensure_future, get_running_loop
from threading import Thread
from time import sleep, time
from typing import Literal


class SuspendDetector(Thread):
    """
    A thread that detects a process continue after a system/process suspend.
    """

    def __init__(self, sleep_time: float = 3.0, lockup_timeout: float = 2.0) -> None:
        """
        Create and (!) start the thread to check for process suspension.
        """
        super().__init__(target=self._loop, name="SuspendDetector", daemon=True)

        self.sleep_time = sleep_time
        self.lockup_timeout = lockup_timeout
        self.lockup_time = self.sleep_time + self.lockup_timeout

        self.loop = get_running_loop()
        self.event = Event()
        self.running = True

        self.start()

    def wait(self) -> Task[Literal[True]]:
        """
        Wait until a continue-after-suspend event happens.
        """
        def inspect_cb(r: Task[Literal[True]]) -> None:
            if r.cancelled:
                self.running = False
            self.event.clear()
        fut = ensure_future(self.event.wait())
        fut.add_done_callback(inspect_cb)
        return fut

    def _loop(self) -> None:
        """
        This internal bit is a bit iffy: our program can suspend between any two lines here. That includes in between
        creating the timestamp and checking it.
        """
        b = time()
        while self.running:
            # Case 1: suspended during time.sleep or case 3
            a = time()
            # Case 2: suspended after determining previous sleep
            if a - b > self.lockup_time:
                self.loop.call_soon_threadsafe(self.event.set)
            b = time()
            # Case 3: suspended while checking for sleep
            if b - a > self.lockup_timeout:
                self.loop.call_soon_threadsafe(self.event.set)
            sleep(self.sleep_time)

    def shutdown(self) -> None:
        """
        Stop listening for suspension events.
        """
        self.running = False


async def main():
    sd = SuspendDetector()
    while True:
        await sd.wait()
        print("DETECTED")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
