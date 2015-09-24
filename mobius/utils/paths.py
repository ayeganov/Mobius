import os

COMM_DIR = "COMM_DIR"
TMP_DIR = "MOBIUS_TMP_DIR"


def get_zmq_dir():
    '''
    Return the folder which contains the communication sockets. Default is
    "/run/shm". Set environment variable COMM_DIR to overwrite the default.
    '''
    return os.environ.get(COMM_DIR, "/run/shm")


def get_tmp_dir():
    '''
    Return the folder to which temporary files could be stored. Default is
    "/run/shm". Set environmente variable TMP_DIR to overwrite the default.
    '''
    return os.environ.get(TMP_DIR, "/run/shm")
