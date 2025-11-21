import logging
from logging.handlers import TimedRotatingFileHandler
import os
import sys

def setup_logging():
    LOG_DIR = "logs"
    os.makedirs(LOG_DIR, exist_ok=True)

    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO) 

    file_handler = TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "app.log"),
        when="midnight", 
        interval=1,
        backupCount=7 
    )
    file_handler.setFormatter(log_formatter)

    # Get the root logger and set its level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO) 

    # Add both handlers to the logger (console and file)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
