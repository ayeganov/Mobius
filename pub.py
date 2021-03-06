import time

from tornado import ioloop
from zmq import eventloop

from mobius.comm.stream import SocketFactory
from mobius.comm.msg_pb2 import UploadFile

eventloop.ioloop.install()

loop = ioloop.IOLoop.instance()


def msg_sent(msg):
    print("Message sent: {0}".format(msg[0].path))


pub_sock = SocketFactory.pub_socket("/upload/ready/", on_send=msg_sent, loop=loop)
print("Address of zmq socket: {0}".format(pub_sock._path))

time.sleep(0.5)
the_file = UploadFile(path="Hello")


def done(future):
    error = future.exception()
    if error is not None:
        print("Oops, error: {0}".format(error))
        return

    print("Message sent successfully.")


#def start_up(executor):
#    result = executor.submit(send_file, sys.argv[1])
#    result.add_done_callback(done)

try:
    pub_sock.send(the_file)
    loop.start()

except (KeyboardInterrupt, SystemExit):
    print("Exiting due to system interrupt...")
