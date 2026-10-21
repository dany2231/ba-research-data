from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path


PROJECT = Path(__file__).resolve().parent

# 토큰과 앱 ID는 저장소에 올리지 않는 local_config.json에서 읽습니다.
# 키: sensortower_token(또는 환경변수 SENSORTOWER_TOKEN), sensortower_apps, sensortower_app_labels, sensortower_countries, sensortower_start
_CONFIG_FILE = PROJECT / "local_config.json"
_CONFIG = json.loads(_CONFIG_FILE.read_text(encoding="utf-8")) if _CONFIG_FILE.exists() else {}
TOKEN = os.environ.get("SENSORTOWER_TOKEN") or _CONFIG.get("sensortower_token", "")
APPS = _CONFIG.get("sensortower_apps") or {
    "ios": [],
    "android": ["com.YostarJP.BlueArchive", "com.nexon.bluearchive"],
}
# 앱 ID별 화면 표시 이름. 없으면 앱 ID를 그대로 표시합니다.
APP_LABELS = _CONFIG.get("sensortower_app_labels") or {}
COUNTRIES = _CONFIG.get("sensortower_countries") or ["JP", "KR", "US", "WW"]
START = _CONFIG.get("sensortower_start", "2021-01-01")
API = "https://api.sensortower.com/v1"
DATA_FILE = PROJECT / "sensortower-data.js"
COUNTRY_LABELS = {"JP": "일본", "KR": "한국", "US": "미국", "TW": "대만", "CN": "중국", "WW": "전 세계"}


def get(path: str, params: dict):
    query = urllib.parse.urlencode({**params, "auth_token": TOKEN})
    request = urllib.request.Request(f"{API}/{path}?{query}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # URL에는 토큰이 들어 있으므로 출력하지 않습니다.
        body = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"{path} HTTP {exc.code}: {body}") from None


def last_full_month_end(today: date):
    first = today.replace(day=1)
    return date.fromordinal(first.toordinal() - 1)


def year_ranges(start: date, end: date):
    current = start
    while current <= end:
        stop = min(date(current.year, 12, 31), end)
        yield current, stop
        current = date(current.year + 1, 1, 1)


def find(term: str):
    for os_name in ("ios", "android"):
        rows = get(f"{os_name}/search_entities", {"entity_type": "app", "term": term, "limit": 10})
        print(f"[{os_name}]")
        for row in rows:
            app_id = row.get("app_id") or row.get("id")
            print(f"  {app_id}\t{row.get('name', '')}\t{row.get('publisher_name', '')}")


def number(row: dict, *keys):
    return sum(row.get(key) or 0 for key in keys)


def fetch():
    end = last_full_month_end(date.today())
    start = date.fromisoformat(START)
    # monthly[국가][YYYY-MM][앱 ID] = {"revenue": USD, "downloads": 건}
    monthly = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"revenue": 0.0, "downloads": 0})))
    app_os = {str(app_id): os_name for os_name, ids in APPS.items() for app_id in ids}
    errors = []

    for os_name, app_ids in APPS.items():
        if not app_ids:
            continue
        for country in COUNTRIES:
            for chunk_start, chunk_end in year_ranges(start, end):
                try:
                    rows = get(f"{os_name}/sales_report_estimates", {
                        "app_ids": ",".join(app_ids),
                        "countries": country,
                        "date_granularity": "monthly",
                        "start_date": chunk_start.isoformat(),
                        "end_date": chunk_end.isoformat(),
                    })
                except RuntimeError as exc:
                    errors.append(f"{os_name} {country} {chunk_start.year}: {exc}")
                    continue
                for row in rows:
                    key = str(row.get("d") or row.get("date") or "")[:7]
                    if len(key) != 7:
                        continue
                    if os_name == "ios":
                        revenue = number(row, "ir", "ar", "revenue")
                        downloads = number(row, "iu", "au", "units")
                    else:
                        revenue = number(row, "r", "revenue")
                        downloads = number(row, "u", "units")
                    # 여러 앱을 한 번에 요청하므로 행의 aid로 앱을 구분합니다.
                    app_id = str(row.get("aid") or row.get("app_id") or "")
                    if app_id not in app_os:
                        errors.append(f"{os_name} {country} {key}: 알 수 없는 앱 ID {app_id!r}")
                        continue
                    cell = monthly[country][key][app_id]
                    # 매출은 센트 단위로 내려옵니다.
                    cell["revenue"] += revenue / 100
                    cell["downloads"] += downloads

    series = {}
    for country, months in monthly.items():
        series[country] = {}
        for key in sorted(months):
            apps = months[key]
            platforms = defaultdict(lambda: {"revenue": 0.0, "downloads": 0})
            for app_id, a in apps.items():
                platforms[app_os[app_id]]["revenue"] += a["revenue"]
                platforms[app_os[app_id]]["downloads"] += a["downloads"]
            series[country][key] = {
                "revenue": round(sum(a["revenue"] for a in apps.values())),
                "downloads": sum(a["downloads"] for a in apps.values()),
                "platforms": {name: {"revenue": round(p["revenue"]), "downloads": p["downloads"]} for name, p in platforms.items()},
                "apps": {app_id: {"revenue": round(a["revenue"]), "downloads": a["downloads"]} for app_id, a in apps.items()},
            }

    data = {
        "source": "Sensor Tower 추정치",
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "range": [start.isoformat()[:7], end.isoformat()[:7]],
        "apps": APPS,
        "appInfo": [{"id": app_id, "os": os_name, "label": APP_LABELS.get(app_id, app_id)} for app_id, os_name in app_os.items()],
        "countries": {c: COUNTRY_LABELS.get(c, c) for c in COUNTRIES if c in series},
        "monthly": series,
    }
    DATA_FILE.write_text("window.SENSORTOWER_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")

    print(json.dumps({
        "range": data["range"],
        "apps": APPS,
        "months": {c: len(v) for c, v in series.items()},
        "errors": errors,
    }, ensure_ascii=False, indent=2))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sensor Tower 월별 매출·다운로드 추정치를 sensortower-data.js로 저장합니다.")
    parser.add_argument("--find", metavar="TERM", help="앱 ID를 검색합니다. 예: --find \"Blue Archive\"")
    args = parser.parse_args()
    if not TOKEN:
        sys.exit("local_config.json의 sensortower_token 또는 환경변수 SENSORTOWER_TOKEN을 설정해 주세요.")
    if args.find:
        find(args.find)
    else:
        fetch()


if __name__ == "__main__":
    main()
