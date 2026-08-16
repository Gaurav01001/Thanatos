from logging import Handler
from logging import Logger
import logging

def get_logging(name: str)-> logging.Logger:
    """ Create and Return a logger for an Engine module """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
        "%(asctime)s | %(levelname) -8s | %(name)s | %(message)s ")

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        return logger