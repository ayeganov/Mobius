import time

from tornado import ioloop
from zmq import eventloop

from mobius.comm.stream import SocketFactory
from mobius.comm.msg_pb2 import UploadFile

eventloop.ioloop.install()

loop = ioloop.IOLoop.instance()


def msg_sent(msg):
    print("Message sent: {0}".format(msg[0].path))

pub = SocketFactory.pub_socket("/upload/ready/", on_send=msg_sent, loop=loop)
print("Address of zmq socket: {0}".format(pub._path))

time.sleep(0.5)
up_file = UploadFile(path="/run/shm/test.bar")
pub.send(up_file)

try:
    loop.start()
except (KeyboardInterrupt, SystemExit):
    print("Exiting due to system interrupt...")
