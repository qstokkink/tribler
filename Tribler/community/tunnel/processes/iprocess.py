from abc import ABCMeta, abstractmethod


class IProcess(object):

    """Generic process interface

    Processes communicate using three data streams (next to std),
    namely:
        * ctrl: for control messages
        * data: for bulk data transfer
        * exit: for exit messages/confirmation

    Note that this separation is made to accommodate the needs
    of the different data streams, which should not interfere with
    each other. These are:
        * ctrl: high message diversity
        * data: high volume
        * exit: low latency
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def on_ctrl(self, s):
        """Callback for when a control message is received

        :param s: the received message
        :type s: str
        :returns: None
        """
        pass

    @abstractmethod
    def on_data(self, s):
        """Callback for when raw data is received

        :param s: the received message
        :type s: str
        :returns: None
        """
        pass

    @abstractmethod
    def on_exit(self, s):
        """Callback for when an exit message is received

        :param s: the received message
        :type s: str
        :returns: None
        """
        pass

    @abstractmethod
    def write_ctrl(self, s):
        """Write a control message to the process

        :param s: the message to send
        :type s: str
        :returns: None
        """
        pass

    @abstractmethod
    def write_data(self, s):
        """Write raw data to the process

        :param s: the data to send
        :type s: str
        :returns: None
        """
        pass

    @abstractmethod
    def write_exit(self, s):
        """Write an exit message to the process

        :param s: the message to send
        :type s: str
        :returns: None
        """
        pass
