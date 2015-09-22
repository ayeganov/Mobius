import logging
import sys

log = logging.getLogger(__name__)

def set_up_logging(log_level=logging.DEBUG, config=None, log_location=None):
    """
    Configure default Mobius logging.

    @param log_level - the initial logging level
    @param config   - a ConfigParser object used to configure the logger objects

    """
    try:
        log_level = logging._levelNames[config.get("Logging", "root")]
    except:
        pass

    # Remove any handlers before calling basicConfig() as it's a no-op otherwise
    root_logger = logging.getLogger()
    if root_logger.handlers:
        map(root_logger.removeHandler, root_logger.handlers)

    if log_location is None:
        # basic config
        logging.basicConfig(
            stream=sys.stderr,
            level=log_level,
            format="%(asctime)s %(process)-05d/%(threadName)-10s [%(name)24s:%(lineno)3d] %(levelname)s: %(message)s")
    else:
        logging.basicConfig(
            filename=log_location,
            level=log_level,
            format="%(asctime)s %(process)-05d/%(threadName)-10s [%(name)24s:%(lineno)3d] %(levelname)s: %(message)s")

    # configure individual loggers
    if config is not None:
        try:
            for name, value in config.items("Logging"):
                logging.getLogger(name).setLevel(logging._levelNames[value])
        except:
            log.exception("Reading logging config")
