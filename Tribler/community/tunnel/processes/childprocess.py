import logging
import sys
from os import environ
from os.path import isfile, join

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.error import ProcessExitedAlready
from twisted.internet.protocol import ProcessProtocol

from Tribler.community.tunnel.processes.iprocess import IProcess
from Tribler.community.tunnel.processes.line_util import pack_data, unpack_complex


class ChildProcess(ProcessProtocol, IProcess):

    """Wrapper for a child process

        Used for creating child processes and communicating
        with them. To be overwritten for advanced
        functionality.
    """

    def __init__(self):
        """Initialize a ChildProcess and spawn it

        This spawns a process in the only multiplatform
        portable way. Using whatever executable and
        whatever environment we are already using.
        Only adding the --tunnel_subprocess arg.

        :returns: None
        """
        self.pid = None

        super(ChildProcess, self).__init__()

        # Raw input buffers
        self.databuffers = {4: "", 6: "", 8: ""}
        # Process is responsive
        self.started = Deferred()
        # One or more of the file descriptors closed unexpectedly
        self.broken = False

        fixed_path = None
        for d in sys.path:
            if isfile(join(d, sys.argv[0])):
                fixed_path = d
                break

        reactor.spawnProcess(self,
                             sys.executable,
                             [sys.executable]
                             + sys.argv + ["--tunnel_subprocess"],
                             env=environ,
                             path=fixed_path,
                             childFDs={
                                 0: 0,   # std in
                                 1: 1,   # std out
                                 2: 2,   # std err
                                 3: "w", # ctrl in
                                 4: "r", # ctrl out
                                 5: "w", # data in
                                 6: "r", # data out
                                 7: "w", # exit in
                                 8: "r"})# exit out

    def write_ctrl(self, s):
        """Write a control message to the process

        :param s: the message to send
        :type s: str
        :returns: None
        """
        reactor.callFromThread(self.raw_write, 3, s)

    def write_data(self, s):
        """Write raw data to the process

        :param s: the message to send
        :type s: str
        :returns: None
        """
        reactor.callFromThread(self.raw_write, 5, s)

    def write_exit(self, s):
        """Write an exit message to the process

        :param s: the message to send
        :type s: str
        :returns: None
        """
        reactor.callFromThread(self.raw_write, 7, s)

    def raw_write(self, fd, data):
        """Write data to a child's file descriptor

        :param fd: the file descriptor to write to
        :type fd: int
        :param data: the data to write
        :type data: str
        :returns: None
        """
        if fd not in self.transport.pipes:
            logging.error("Dropping message for FD " + str(fd)
                          + ", pipe is closed")
        else:
            self.transport.writeToChild(fd, pack_data(data))

    def connectionMade(self):
        """Notify users that this process is ready to go

        :returns: None
        """
        self.pid = self.transport.pid
        # Allow some time for the process to capture its streams
        reactor.callLater(1.0, self.started.callback, self)

    def childDataReceived(self, childFD, data):
        """Fired when the process sends us something

        :param childFD: the file descriptor which was used
        :type childFD: int
        :param data: the data which was sent
        :type data: str
        :returns: None
        """
        partitions = data.split('\n')
        for partition in partitions[:-1]:
            concat_data = self.databuffers.get(childFD, "")\
                          + partition + '\n'
            cc_data, out = unpack_complex(concat_data)
            self.databuffers[childFD] = cc_data
            if out is not None:
                if childFD == 4:
                    # ctrl out
                    reactor.callInThread(self.on_ctrl, out)
                    self.databuffers[childFD] = ""
                elif childFD == 6:
                    # data out
                    reactor.callInThread(self.on_data, out)
                    self.databuffers[childFD] = ""
                elif childFD == 8:
                    # exit out
                    reactor.callInThread(self.on_exit, out)
                    self.databuffers[childFD] = ""
                else:
                    logging.error("Got data on unknown FD "
                                  + str(childFD))
        self.databuffers[childFD] += partitions[-1]

    def childConnectionLost(self, childFD):
        """Fired when a childFD is closed

        This is probably the result of a process shutdown

        :param childFD: the file descriptor which closed
        :type childFD: int
        :returns: None
        """
        self.broken = True
        logging.info("[" + str(self.pid)
                     + "] Connection lost with child FD "
                     + str(childFD))
        self.transport.closeChildFD(childFD)

    def processEnded(self, status):
        """Fired when the process ends

        :param status: the exit status
        :type status: twisted.python.failure.Failure
        :returns: None
        """
        for i in range(9):
            self.transport.closeChildFD(i)

    def terminate(self):
        """Terminate this process forcefully

        :returns: None
        """
        try:
            self.transport.signalProcess('KILL')
        except ProcessExitedAlready:
            pass
