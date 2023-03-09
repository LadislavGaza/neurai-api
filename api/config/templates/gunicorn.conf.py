import multiprocessing

bind = "0.0.0.0:8080"
workers = 1 # multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
loglevel = "info"
reload = True
max_requests = 1
reload_engine = "auto"

