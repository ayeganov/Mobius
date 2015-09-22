import abc


class ICommand(metaclass=abc.ABCMeta):
    """
    This is the interface that all commands must implement to work with mobius
    worker services.
    """
    @abc.abstractmethod
    def execute(self):
        """
        Execute this command.
        """
