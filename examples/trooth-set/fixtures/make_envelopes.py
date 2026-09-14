"""Refresh the fixtures: Trooth-shaped envelopes from Trooth's own catalog sources.

    uv run python examples/trooth-set/fixtures/make_envelopes.py

Trooth's `/fetch` endpoint, which would serve these signed by Trooth, is not public yet. So
this script does what Trooth's `jobs/snapshot.py` does - fetch each catalog endpoint, hash
the bytes, stamp the fetch time - and wraps the result in the envelope shape of
`schema/envelope/v0.1.json`, **signed by a local ed25519 key with `key_id: kourob-local`**.
That key id is the honest marker: these envelopes prove what was fetched and when, by this
operator, not by Trooth. Swap them for real ones the day `/fetch` is live; nothing
downstream changes.

The payload normalisation (a station's fields, a quake list, a CPI reading) is the part
Trooth would do in its API. It is kept small and obvious here.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from kourob import identity

HERE = Path(__file__).resolve().parent
OUT = HERE / "envelopes"
USER_AGENT = "(kourob-trooth-set fixtures, https://github.com/alexchouck-hash/kourob)"

SOURCES = {
    "nws": {
        "query": "weather/observations/KJFK",
        "url": "https://api.weather.gov/stations/KJFK/observations/latest",
        "headers": {"Accept": "application/geo+json"},
        "license": "public-domain",
        "considered_and_rejected": [{"id": "open-meteo", "reason": "derivative of nws"}],
    },
    "open-meteo": {
        "query": "weather/current/40.64,-73.78",
        "url": "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode(
            {
                "latitude": 40.64,
                "longitude": -73.78,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m",
            }
        ),
        "headers": {},
        "license": "CC-BY-4.0",
        "considered_and_rejected": [{"id": "nws", "reason": "primary; asked for the model grid"}],
    },
    "usgs-earthquake": {
        "query": "seismic/earthquakes/past_hour",
        "url": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
        "headers": {},
        "license": "public-domain",
        "considered_and_rejected": [],
    },
    "bls": {
        "query": "economy/cpi/CUUR0000SA0",
        "url": "https://api.bls.gov/publicAPI/v1/timeseries/data/CUUR0000SA0",
        "headers": {},
        "license": "public-domain",
        "considered_and_rejected": [{"id": "fred", "reason": "derivative of bls for CPI"}],
    },
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise(source: str, payload: dict) -> tuple[dict, str]:
    """(data, source_timestamp). The shape Trooth would hand back for this query."""
    if source == "nws":
        p = payload["properties"]
        return (
            {
                "location": "KJFK",
                "temperature_c": p["temperature"]["value"],
                "relative_humidity_pct": p["relativeHumidity"]["value"],
                "wind_speed_kmh": p["windSpeed"]["value"],
                "conditions": p.get("textDescription") or "",
            },
            p["timestamp"],
        )
    if source == "open-meteo":
        c = payload["current"]
        return (
            {
                "location": "KJFK",
                "temperature_c": c["temperature_2m"],
                "relative_humidity_pct": c["relative_humidity_2m"],
                "wind_speed_kmh": c["wind_speed_10m"],
                "conditions": "",
            },
            c["time"] + ":00Z",
        )
    if source == "usgs-earthquake":
        feats = payload["features"]
        quakes = [
            {
                "id": f["id"],
                "mag": f["properties"]["mag"],
                "place": f["properties"]["place"],
                "time": _iso(datetime.fromtimestamp(f["properties"]["time"] / 1000, UTC)),
                "depth_km": f["geometry"]["coordinates"][2],
            }
            for f in feats
            if f["properties"].get("mag") is not None
        ]
        largest = max(quakes, key=lambda q: q["mag"], default=None)
        generated = _iso(datetime.fromtimestamp(payload["metadata"]["generated"] / 1000, UTC))
        return (
            {"window": "past_hour", "count": len(quakes), "largest": largest, "quakes": quakes},
            generated,
        )
    if source == "bls":
        series = payload["Results"]["series"][0]
        latest = series["data"][0]
        month = int(latest["period"][1:])
        return (
            {
                "series_id": series["seriesID"],
                "series_name": "CPI-U, all items, U.S. city average, not seasonally adjusted",
                "year": int(latest["year"]),
                "period": latest["period"],
                "period_name": latest["periodName"],
                "value": float(latest["value"]),
            },
            f"{latest['year']}-{month:02d}-01T00:00:00Z",
        )
    raise ValueError(source)


def fetch(source: str, cfg: dict) -> dict:
    request = urllib.request.Request(
        cfg["url"], headers={"User-Agent": USER_AGENT, **cfg["headers"]}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    fetched = datetime.now(UTC)
    payload = json.loads(raw.decode("utf-8"))
    data, source_ts = _normalise(source, payload)
    lag = max(
        0.0, (fetched - datetime.fromisoformat(source_ts.replace("Z", "+00:00"))).total_seconds()
    )
    return {
        "schema_version": "0.1",
        "request_id": "req_" + hashlib.sha256(raw).hexdigest()[:24],
        "data": data,
        "provenance": {
            "resolved_query": cfg["query"],
            "served_from": "live",
            "snapshot_id": f"snap_{fetched:%Y%m%dT%H%M%SZ}_{source}",
            "sources": [
                {
                    "id": source,
                    "role": "primary",
                    "url": cfg["url"],
                    "license": cfg["license"],
                    "source_timestamp": source_ts,
                    "fetched_at": _iso(fetched),
                    "freshness_lag_s": round(lag, 1),
                    "content_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
                }
            ],
            "considered_and_rejected": cfg["considered_and_rejected"],
            "scorecard_ref": f"https://alexchouck-hash.github.io/trooth-site/scorecards/{source}",
            "untrusted_text": [data["conditions"]] if data.get("conditions") else [],
            "quota": {"remaining": 0, "cost_units": 1},
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        identity.generate(Path(tmp))
        key = identity.load_private_key(Path(tmp))
        did = identity.load_did(Path(tmp))
        for source, cfg in SOURCES.items():
            envelope = fetch(source, cfg)
            signature = identity.sign(
                key, {"data": envelope["data"], "provenance": envelope["provenance"]}
            )
            envelope["signature"] = {"alg": "ed25519", "key_id": "kourob-local", "sig": signature}
            envelope["log"] = {"entry_id": did, "checkpoint": "local-unsigned-by-trooth"}
            path = OUT / f"{source}.json"
            path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            stamp = envelope["provenance"]["sources"][0]["source_timestamp"]
            print(f"{source:<16} {stamp}  -> {path.name}")


if __name__ == "__main__":
    main()
