from mobius.comm.msg_pb2 import UploadFile
from mobius.comm.stream import SocketFactory

from zmq.eventloop import IOLoop


def got_msgs(msgs):
    print(msgs)

loop = IOLoop.instance()
dealer = SocketFactory.dealer_socket("/upload/ready/", on_recv=got_msgs, bind=False, loop=loop)


def send_msg(loop, sock):
    msg = UploadFile(path="Google!")
    sock.send(msg)
    loop.call_later(1, send_msg, loop, sock)

loop.call_later(1, send_msg, loop, dealer)

loop.start()
