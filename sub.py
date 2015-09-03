from tornado import ioloop
from zmq import eventloop

from mobius.comm.stream import SocketFactory

eventloop.ioloop.install()

loop = ioloop.IOLoop.instance()


def msg_received(msg):
    print("Message received: {0}".format(msg[0].path))

sub = SocketFactory.sub_socket("/upload/ready/", on_recv=msg_received, loop=loop)
print("Address of zmq socket: {0}".format(sub._path))

try:
    loop.start()
except (KeyboardInterrupt, SystemExit):
    print("Exiting due to system interrupt...")
