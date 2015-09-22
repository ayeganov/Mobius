import logging

from zmq.eventloop import IOLoop

from mobius.comm import stream
from mobius.utils import set_up_logging

log = logging.getLogger(__name__)


def main():
    try:
        set_up_logging()
        loop = IOLoop.instance()
        proxy = stream.RouterPubSubProxy(front="/request/request",
                                         back_out="/request/do_work",
                                         back_in="/request/result",
                                         loop=loop)
        log.info("Starting the server proxy.")
        proxy.start()
    except (SystemExit, KeyboardInterrupt):
        print("Exiting due to system interrupt...")


if __name__ == "__main__":
    main()
