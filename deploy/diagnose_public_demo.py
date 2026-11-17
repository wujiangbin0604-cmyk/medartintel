"""Read-only public HTTP diagnosis; never claims that local success proves deployment."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def request(opener, url, payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=7) as response:
            raw = response.read(500000).decode("utf-8", "replace")
            result = {"status": response.status, "content_type": response.headers.get("Content-Type")}
            try: result["json"] = json.loads(raw)
            except json.JSONDecodeError: result["html_present"] = "<html" in raw.lower()
            return result
    except urllib.error.HTTPError as error:
        return {"status": error.code, "error_type": "HTTPError", "server": error.headers.get("Server"),
                "body_excerpt": error.read(200).decode("utf-8", "replace")}
    except Exception as error:
        return {"status": None, "error_type": type(error).__name__, "message": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://47.83.150.55:8000")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/final_validation/public_probe.json")
    args = parser.parse_args()
    checks = {}
    for mode, opener in [("configured_network", urllib.request.build_opener()),
                         ("direct_connection", urllib.request.build_opener(urllib.request.ProxyHandler({})))]:
        result = {"health": request(opener, args.url + "/api/health"),
                  "dashboard": request(opener, args.url + "/dashboard")}
        if result["health"].get("status") == 200 and result["health"].get("json", {}).get("models_loaded") == 6:
            marks = request(opener, args.url + "/api/ecg/annotations?record_id=200&start_sec=6&duration_sec=10&task=nv")
            candidates = [m for m in marks.get("json", {}).get("annotations", []) if m.get("within_task")]
            if candidates:
                result["inference"] = request(opener, args.url + "/api/inference/beat", {
                    "record_id": "200", "annotation_sample": candidates[0]["annotation_sample"], "task": "nv", "model_id": "cnn_1d"})
                local_hash = hashlib.sha256((ROOT / "checkpoints/nv44_v1/formal/cnn/cnn_final_best.pt").read_bytes()).hexdigest()
                result["deployed_checkpoint_matches_local"] = result["inference"].get("json", {}).get("model_sha256") == local_hash
        checks[mode] = result
    data = {"checked_at_Asia_Shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "url": args.url, "checks": checks,
            "public_http_inference_verified": any(v.get("inference", {}).get("status") == 200 and v.get("deployed_checkpoint_matches_local") for v in checks.values()),
            "public_browser_flow_verified": False, "server_changes_made": False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
