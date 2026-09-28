from ipv8.taskmanager import TaskManager
from ipv8.test.base import TestBase

from tribler.core.libtorrent.download_manager.suspend_detector import SuspendDetector


class TestSuspendDetector(TestBase):
    """
    Tests for the SuspendDetector class.
    """

    async def setUp(self) -> None:
        """
        Create a new mocked stream chunk.
        """
        super().setUp()

        self.tm = TaskManager()
        self.sd = SuspendDetector(0.01)

    def test_shutdown(self) -> None:
        """
        Test if we can do a clean shutdown.
        """
        self.sd.shutdown()
        self.sd.join()

    async def test_shutdown_cancel(self) -> None:
        """
        Test if we can do a clean shutdown by Future cancellation.
        """
        _ = self.tm.register_task("test", self.sd.wait())
        await self.tm.shutdown_task_manager()
        self.sd.join()
