# src/logging_config.py
import logging
import logging.handlers
import os
from datetime import datetime

def setup_logging():
    """
    Configure logging with rotation based on time (12 hours) and format
    Logs will be stored in /var/log/auto-hpa/ for container compatibility
    """
    # Create logs directory if it doesn't exist
    log_dir = "/var/log/auto-hpa"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure logging
    log_file = os.path.join(log_dir, "controller.log")
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Create TimedRotatingFileHandler
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_file,
        when='H',        # Rotate every hour
        interval=12,     # Keep logs for 12 hours
        backupCount=1,   # Keep one backup file
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    
    # Create console handler for container logs
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.info("Auto-HPA controller logging initialized with 12-hour rotation")
