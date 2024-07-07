import gevent.monkey
gevent.monkey.patch_all()

debug = True
workers = 5
worker_class = "gevent"
bind = '0.0.0.0:$PORT'
