import errno
import functools
import logging

import zmq
import zmq.eventloop

log = logging.getLogger(__name__)


def eventloop(func):
    """
    Wraps a function and invokes a ZMQ eventloop.

    The intention of this decorator is to provide a standard way of starting up
    code that runs with the ZMQ eventloop. The main issue here is that ZMQ
    occassionally receives a EINTR error when creating a socket connection or
    communicating via a socket and this will not be handled by tornado.

    The following shows a simple example of how to use the decorator.

        def foo():
            print('foo')

        @eventloop
        def frobnicator(loop):
            pub = zmq.eventloop.PeriodicCallback(
                    foo,
                    1000,
                    io_loop=loop)
            pub.start()

        frobnicator()

    This will result in 'foo' being written to stdout once per second.

    """
    @functools.wraps(func)
    def impl(loop=None):
        loop = zmq.eventloop.IOLoop.instance() if loop is None else loop
        while True:
            try:
                func(loop)
                loop.start()
                break
            except zmq.ZMQError as e:
                if e.errno == errno.EINTR:
                    continue
                log.exception(e)
                break
            except Exception as e:
                log.exception(e)
                break
            except (SystemExit, KeyboardInterrupt):
                log.info('Exiting due to interrupt')
                break

    return impl
