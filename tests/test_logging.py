from engine.core.logging import get_logging

def test_logging_creation():

    logger = get_logging("test")

    assert logger.name == "test"
    assert logger.level > 0