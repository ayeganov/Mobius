from mobius.comm.stream import SocketFactory
from zmq.eventloop import IOLoop


def got_msgs(msgs):
    print(msgs)

loop = IOLoop.instance()
router = SocketFactory.router_socket("/upload/ready/", on_recv=got_msgs, bind=True, loop=loop)

loop.start()
