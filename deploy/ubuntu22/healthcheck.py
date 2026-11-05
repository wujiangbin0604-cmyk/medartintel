"""Container health requires the original six models, not only an HTTP 200."""
import json
import sys
from urllib.request import urlopen


def main():
    with urlopen("http://127.0.0.1:8000/api/health", timeout=8) as response:
        health = json.load(response)
    if health.get("status") != "ok" or health.get("models_loaded") != 6 or health.get("models_total") != 6:
        print(json.dumps(health), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
