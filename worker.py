
from zmq.eventloop import IOLoop, ioloop

from mobius.comm import stream
from mobius.comm.msg_pb2 import Response
from mobius.service import TEST


loop = IOLoop.instance()


def msg_sent(msgs):
    msg = msgs[-1]
    print("Sending message: {0}".format(str(msg)))

def msg_rcvd(msgs):
    request_id, server_id, msg = msgs
    print("Sweet, got a message back: {0}".format(str(msg)))
    response = Response(service_name="TEST", response=msg.data)
    response_pub.reply([request_id, server_id], response)


work_sub = stream.SocketFactory.sub_socket("/request/do_work", on_recv=msg_rcvd, bind=False, loop=loop)
response_pub = stream.SocketFactory.pub_socket("/request/result", on_send=msg_sent, bind=False, loop=loop)

loop.start()
