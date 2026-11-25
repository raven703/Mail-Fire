"""Real HTTP boundary with real preload/fork broker; disposable image only."""
import concurrent.futures
import json
import threading
import urllib.error
import urllib.request


def test_http_analysis_and_backpressure():
    from app import parser_service as service
    from app.analysis_broker import AnalysisBroker
    import runpy
    payload = runpy.run_path('/app/tests/test_unified_analysis.py')['mail_payload']
    service.UNIFIED = True
    service.broker = AnalysisBroker()
    server = service.Server(('127.0.0.1', 0), service.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:%d/analyze' % server.server_port

    def post(value):
        request = urllib.request.Request(url, json.dumps(value).encode(), {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    try:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(post, [payload('one', False), payload('two', False)]))
        assert [r[0] for r in results] == [200, 200]
        assert [r[1]['parsed']['subject'] for r in results] == ['one', 'two']
        assert post([])[0] == 422
        # HTTP body delivery can precede the handler's finally/release.
        import time
        time.sleep(.1)
        acquired = 0
        while service.admission.acquire(False):
            acquired += 1
        try:
            assert post(payload('busy', False))[0] == 429
        finally:
            for _ in range(acquired):
                service.admission.release()
        assert post(payload('recovered', False))[0] == 200
        import os
        import signal
        os.kill(service.broker.process.pid, signal.SIGKILL)
        service.broker.process.wait(timeout=10)
        assert post(payload('restart', False))[0] == 503
        assert post(payload('retry', False))[0] == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        service.broker.close()