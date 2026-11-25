"""Fault-injection entrypoint for a disposable parser container only."""
import os
import runpy
import threading
import time


def inject():
    while not os.path.exists('/fault/trigger'):
        time.sleep(.05)
    os.unlink('/fault/trigger')
    memory = []
    while True:
        memory.append(bytearray(16 * 1024**2))


threading.Thread(target=inject, daemon=True).start()
runpy.run_module('app.parser_service', run_name='__main__')