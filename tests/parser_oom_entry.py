"""Fault-injection entrypoint for a disposable parser container only."""
import os
import runpy
import threading
import time

# Hold only the first real analysis request at the broker boundary so the
# external test can prove RUNNING ownership before triggering cgroup OOM.
from app.analysis_broker import AnalysisBroker
original_analyze = AnalysisBroker.analyze


def analyze(self, request):
    if not os.path.exists('/fault/injected'):
        with open('/fault/analysis-started', 'w'):
            pass
        while True:
            time.sleep(.05)
    return original_analyze(self, request)


AnalysisBroker.analyze = analyze


def inject():
    while not os.path.exists('/fault/trigger'):
        time.sleep(.05)
    os.unlink('/fault/trigger')
    with open('/fault/injected', 'w'):
        pass
    memory = []
    while True:
        memory.append(bytearray(16 * 1024**2))


threading.Thread(target=inject, daemon=True).start()
runpy.run_module('app.parser_service', run_name='__main__')