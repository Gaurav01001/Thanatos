from engine.core.logging import get_logging

logger = get_logging("engine")

def main()-> None:
    logger.info("Thanatos Starting...")



if __name__ == "__main__":
    main()
else:
    logger.info("Thanatos Already Started...")