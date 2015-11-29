import zmq

from mobius.comm.msg_pb2 import WorkerState


ctx = zmq.Context.instance()
sock = ctx.socket(zmq.SUB)
sock.setsockopt(zmq.SUBSCRIBE, b"")

sock.bind("ipc:///run/shm/worker_state_Test")


try:
    print("Waiting for data on {}...".format("ipc:///run/shm/worker_state_Test"))
    while True:
        msg = sock.recv_multipart()[-1]
#        ws = WorkerState()
#        ws.ParseFromString(msg)
        print("Got {}".format(msg))
except (KeyboardInterrupt, SystemExit):
    print("Exiting due to system interrupt...")
