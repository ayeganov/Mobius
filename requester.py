from zmq.eventloop import IOLoop, ioloop

from mobius.comm import stream
from mobius.comm.msg_pb2 import Request
from mobius.service import TEST


loop = IOLoop.instance()


def msg_sent(msgs):
    msg = msgs[-1]
    print("Sending message: {0}".format(str(msg)))

def msg_rcvd(msgs):
    msg = msgs[-1]
    print("Sweet, got a message back: {0}".format(str(msg)))

proxy = stream.LocalRequestProxy("/request/local", "request/request", loop)
dealer = stream.SocketFactory.dealer_socket("/request/local", on_send=msg_sent, transport=stream.INPROC, on_recv=msg_rcvd, bind=False, loop=loop)

msg_count = 0

def send_message():
    global msg_count
    request = Request(type=TEST, data=str(msg_count))
    dealer.send(request)
    msg_count += 1

periodic_sender = ioloop.PeriodicCallback(send_message, 20000, loop)
periodic_sender.start()

loop.start()
