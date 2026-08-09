# -*- coding: utf-8 -*-

import os
from pathlib import Path

try:
    import config.custom_config_local as custom_config
except ImportError:
    import config.custom_config as custom_config


os.makedirs(custom_config.LOG_PATH, exist_ok=True)


workers = custom_config.WORKERS

worker_class = "gevent"

# Render uses dynamic PORT
bind = f"0.0.0.0:{os.environ.get('PORT', 2012)}"


accesslog = str(
    Path(custom_config.LOG_PATH, "gunicorn_access.log").resolve()
)

errorlog = str(
    Path(custom_config.LOG_PATH, "gunicorn.log").resolve()
)


loglevel = "info"

reload = False

timeout = 60


access_log_format = (
    '%(t)s %(l)s %({X-Real-IP}i)s '
    '"%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
)
