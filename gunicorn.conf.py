# Gunicorn configuration for production
# Usage: gunicorn kairos_project.wsgi:application -c gunicorn.conf.py

import multiprocessing
import os

# Bind
bind = "0.0.0.0:" + os.getenv("PORT", "8000")

# Workers: 2-4 x CPU cores (for a small Oracle VM, 2 is fine)
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))

# Timeout (DeepSeek API can take 10-30s, be generous)
timeout = 120

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Graceful restart
graceful_timeout = 30
