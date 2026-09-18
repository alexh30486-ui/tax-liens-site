"""
Gunicorn config — Uvicorn worker class for FastAPI.

Run from backend/ directory:
  PYTHONPATH=src gunicorn -c ../deploy/gunicorn/gunicorn.conf.py app.main:app
"""

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count())))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
timeout = 60
keepalive = 5
graceful_timeout = 30
max_requests = 2000
max_requests_jitter = 100
preload_app = False
accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
capture_output = True
# Do not put secrets in this file — load from environment / systemd EnvironmentFile
