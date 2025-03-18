import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(app):
    # Ensure logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure file handler
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=1024 * 1024,  # 1MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    
    # Configure app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')
