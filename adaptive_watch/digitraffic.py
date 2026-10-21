"""Finnish road weather cameras with co-located visibility sensors (Fintraffic / digitraffic.fi, CC BY 4.0).

External, real-weather test set for the visibility task. Labels come from an
instrument, not from looking at the image: the road weather station's present-weather
visibility (NÄKYVYYS_M) at most 10 minutes from the image's capture time.

- positive (fog / low visibility): visibility < 1000 m (meteorological fog threshold)
- negative: visibility >= 5000 m
- 1000–5000 m: logged, never labelled

Image history is kept by the API for 24 h only and visibility is live only, so the
collector polls forward every 10 minutes. Source: Fintraffic / digitraffic.fi, licence CC 4.0 BY.
"""

from __future__ import annotations

import gzip
import json
import math
import os
import random
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(os.environ.get("AW_DATA", Path.home() / ".cache" / "adaptive-watch" / "data")) / "digitraffic"
API = "https://tie.digitraffic.fi/api"
USER = "hafnia-hackathon-2026-research"
MAX_SENSOR_KM = 0.2
POSITIVE_M, NEGATIVE_M = 1000.0, 5000.0
MAX_SKEW_S = 600
NEGATIVE_EVERY_S = 6 * 3600  # per camera: at most one clear-weather image per 6 h


def _get(url: str, raw: bool = False):
    req = urllib.request.Request(url, headers={"Digitraffic-User": USER, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return (body, r.headers) if raw else json.loads(body)


def _km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def camera_set() -> list[dict]:
    """Frozen on first use: gathering cameras within MAX_SENSOR_KM of a station reporting NÄKYVYYS_M."""
    path = ROOT / "cameras.json"
    if path.exists():
        return json.loads(path.read_text())
    cams = _get(f"{API}/weathercam/v1/stations")["features"]
    stations = {f["id"]: f["geometry"]["coordinates"] for f in _get(f"{API}/weather/v1/stations")["features"]}
    data = _get(f"{API}/weather/v1/stations/data")["stations"]
    with_vis = {s["id"] for s in data for v in s.get("sensorValues", []) if v["name"] == "NÄKYVYYS_M"}
    out = []
    for f in cams:
        p = f["properties"]
        presets = [x for x in p.get("presets", []) if x.get("inCollection")]
        if p.get("collectionStatus") != "GATHERING" or not presets:
            continue
        sid, km = min(((s, _km(f["geometry"]["coordinates"], stations[s])) for s in with_vis if s in stations),
                      key=lambda x: x[1])
        if km <= MAX_SENSOR_KM:
            out.append({"camera": p["id"], "preset": presets[0]["id"], "station": sid, "km": round(km, 3),
                        "lon_lat": f["geometry"]["coordinates"][:2]})
    ROOT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out


def _visibility() -> dict[int, tuple[float, str]]:
    data = _get(f"{API}/weather/v1/stations/data")["stations"]
    return {s["id"]: (float(v["value"]), v["measuredTime"]) for s in data for v in s.get("sensorValues", [])
            if v["name"] == "NÄKYVYYS_M" and v.get("measuredTime")}


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect_once(cams: list[dict], last_negative: dict[str, float], rng: random.Random) -> dict:
    now = datetime.now(timezone.utc)
    vis = _visibility()
    with (ROOT / "readings.jsonl").open("a") as f:
        for c in cams:
            if c["station"] in vis:
                v, t = vis[c["station"]]
                f.write(json.dumps({"camera": c["camera"], "station": c["station"], "visibility_m": v,
                                    "measured": t, "polled": now.isoformat()}) + "\n")
    stats = {"polled": now.isoformat(), "positive": 0, "negative": 0, "skipped_skew": 0, "errors": 0}
    order = cams[:]
    rng.shuffle(order)
    for c in order:
        if c["station"] not in vis:
            continue
        v, measured = vis[c["station"]]
        if v < POSITIVE_M:
            label = 1
        elif v >= NEGATIVE_M and now.timestamp() - last_negative.get(c["camera"], 0) >= NEGATIVE_EVERY_S:
            label = 0
        else:
            continue
        try:
            body, headers = _get(f"https://weathercam.digitraffic.fi/{c['preset']}.jpg", raw=True)
        except Exception:  # network errors are counted, never fatal; the next cycle tries again
            stats["errors"] += 1
            continue
        captured = parsedate_to_datetime(headers["Last-Modified"]).astimezone(timezone.utc)
        skew = abs((captured - _ts(measured)).total_seconds())
        if skew > MAX_SKEW_S:
            stats["skipped_skew"] += 1
            continue
        d = ROOT / "images" / c["camera"]
        d.mkdir(parents=True, exist_ok=True)
        name = f"{c['preset']}_{captured.strftime('%Y%m%dT%H%M%SZ')}.jpg"
        if (d / name).exists():
            continue  # same capture as a previous cycle
        (d / name).write_bytes(body)
        with (ROOT / "index.jsonl").open("a") as f:
            f.write(json.dumps({"file": f"{c['camera']}/{name}", "camera": c["camera"], "preset": c["preset"],
                                "captured": captured.isoformat(), "visibility_m": v, "measured": measured,
                                "skew_s": skew, "label": label}) + "\n")
        if label == 0:
            last_negative[c["camera"]] = now.timestamp()
        stats["positive" if label else "negative"] += 1
    return stats


def collect(hours: float, interval_s: int = 600) -> None:
    cams = camera_set()
    print(f"{len(cams)} cameras within {MAX_SENSOR_KM} km of a visibility sensor; data in {ROOT}", flush=True)
    last_negative: dict[str, float] = {}
    idx = ROOT / "index.jsonl"
    if idx.exists():
        for line in idx.read_text().splitlines():
            r = json.loads(line)
            if r["label"] == 0:
                last_negative[r["camera"]] = max(last_negative.get(r["camera"], 0), _ts(r["captured"]).timestamp())
    rng, deadline = random.Random(0), time.time() + hours * 3600
    while time.time() < deadline:
        t0 = time.time()
        try:
            print(json.dumps(collect_once(cams, last_negative, rng)), flush=True)
        except Exception as exc:  # keep polling through transient API failures
            print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), flush=True)
        time.sleep(max(0, interval_s - (time.time() - t0)))
