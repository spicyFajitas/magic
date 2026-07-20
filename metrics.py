import threading
from prometheus_client import Counter, Histogram, start_http_server

ANALYSES_STARTED = Counter("edhrec_analyses_started_total", "Total deck analyses started")
ANALYSES_COMPLETED = Counter("edhrec_analyses_completed_total", "Total deck analyses completed successfully")
ANALYSES_FAILED = Counter("edhrec_analyses_failed_total", "Total deck analyses failed")
ANALYSIS_DURATION = Histogram(
    "edhrec_analysis_duration_seconds",
    "End-to-end analysis duration in seconds",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)


def _start_server():
    try:
        start_http_server(8502)
    except OSError:
        pass  # already started by a previous import


threading.Thread(target=_start_server, daemon=True).start()
