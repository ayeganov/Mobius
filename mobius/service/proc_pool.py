# The purpose of this module is to start multiple processes, and establish a
# communication method to receive information back from the children workers.
import abc
import multiprocessing as mp


class ProcPool:
    '''
    Process pool that allows a one way communication - from the spawned
    processes to the parent process.
    '''
    def __init__(self, num_procs):
        self._comm_queue = mp.Queue()
        self._pool = mp.Pool(num_procs)
        self._results = {}

    def wait(self):
        '''
        Wait for all jobs to finish.
        '''
        self._pool.join()

    def submit(self, runnable, args=()):
        runnable._msg_queue = self._comm_queue
        return self._pool.apply_async(runnable, args)


class MobiusProcess(metaclass=abc.ABCMeta):
    '''
    Mobius command that runs in a separate process, and is able to communicate
    back to the parent process.
    '''
    @abc.abstractmethod
    def __call__(self):
        '''
        Run this command.
        '''

    @abc.abstractproperty
    def id(self):
        '''
        Mobius id of this process - NOT pid.
        '''

    @abc.abstractproperty
    def _msg_queue(self):
        '''
        The queue to communicate back with the parent process.
        '''

    def send_async_data(self, data):
        '''
        Send data back to the parent process.

        @param data - Data to be sent to the parent process. Must be
                      picklable.
        '''
        self._msg_queue.put_nowait((self.id, data))


import time
class TestProcess(MobiusProcess):
    def __init__(self, mob_id, data_in):
        self._data_in = data_in
        self._id = mob_id
        self._queue = None

    @property
    def id(self):
        return self._id

    @property
    def _msg_queue(self):
        return self._queue

    @_msg_queue.setter
    def _msg_queue(self, new_q):
        self._queue = new_q

    def __call__(self):
        print("Doing work with {}".format(self._data_in))
        self.send_async_data("I am done")
        time.sleep(1)
        return self._data_in * 5


def main():
    proc_pool = ProcPool(5)

    future = proc_pool.submit(TestProcess(1, 5))
    future.add_done_callback(lambda f: print(f.result()))
    proc_pool.wait()


if __name__ == "__main__":
    main()
