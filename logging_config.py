# logging_config.py

import logging
import socket
from mpi4py import MPI

def configure_logger():
    rank = MPI.COMM_WORLD.Get_rank()
    hostname = socket.gethostname()

    logging.basicConfig(
        filename=f'mpi_log_rank_{rank}_{hostname}.log',
        level=logging.INFO,
        format='%(asctime)s - Rank %(rank)d - %(hostname)s - %(message)s',
        filemode='w'
    )

    logger = logging.getLogger()
    return logging.LoggerAdapter(logger, {'rank': rank, 'hostname': hostname})
