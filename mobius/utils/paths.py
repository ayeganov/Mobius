import os

COMM_DIR = "COMM_DIR"


def get_comm_dir():
    '''
    Return the folder which contains the communication sockets.
    '''
    return os.environ.get(COMM_DIR, "/run/shm")
