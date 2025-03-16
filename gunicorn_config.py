import os
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 120
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log errors to stdout
loglevel = "info"
