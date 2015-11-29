import multiprocessing as mp
import time
import unittest

import zmq

from mobius.comm.stream import Socket
from mobius.comm import msg_pb2


class Worker:
    def __init__(self):
        self._work_state = Socket("/worker/state/Test", sock_type=zmq.DEALER, bind=False)

    def run(self):
        msgs = (msg_pb2.WorkerState(progress=v) for v in range(1, 101))
        for msg in msgs:
            self._work_state.send(msg)
            time.sleep(0.002)


class Manager:
    def __init__(self):
        self._work_state = Socket("/worker/state/Test", sock_type=zmq.ROUTER, bind=True)
        self.received = []

    def start(self):
        _, msgs = self._work_state.recv()
        msg = msgs[-1]
        while msg.progress < 100:
            self.received.append(msg.progress)
            _, msgs = self._work_state.recv()
            msg = msgs[-1]
        self.received.append(msg.progress)


def do_work():
    try:
        worker = Worker()
        worker.run()
    except Exception as e:
        print("Worker: {}".format(e))


def expect_results():
    try:
        manager = Manager()
        manager.start()
        return manager.received
    except Exception as e:
        print("Manager: {}".format(e))


class SocketToStreamCommunication(unittest.TestCase):
    '''
    Verifies that the socket is able to communicate with the stream socket.
    '''
    def test_one_way_communication(self):
        process = mp.Process(target=do_work)
        process.start()
        progress = expect_results()
        process.join()
        process.terminate()
        self.assertEqual(progress, list(range(1, 101)))


if __name__ == "__main__":
    unittest.main()
