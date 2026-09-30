import os
bind = '0.0.0.0:' + os.environ.get('PORT', '8000')
workers = int(os.environ.get('WEB_CONCURRENCY', '2'))
timeout = 90
errorlog = '-'
# Avoid writing request URLs or submitted personal information to access logs.
accesslog = None
