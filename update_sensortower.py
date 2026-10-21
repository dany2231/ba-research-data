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
DAILY_FILE = PROJECT / "sensortower-daily.js"
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


# 일 단위 순위는 국가별 매출 차트(게임 카테고리)에서 가져옵니다. 전 세계(WW) 순위는 없습니다.
RANK_CHARTS = {"ios": ("6014", "topgrossingapplications"), "android": ("game", "topgrossing")}


def app_key(row: dict):
    return str(row.get("aid") or row.get("app_id") or "")


def day_key(row: dict):
    return str(row.get("d") or row.get("date") or "")[:10]


def sales_values(os_name: str, row: dict):
    # 매출은 센트 단위로 내려옵니다.
    if os_name == "ios":
        return number(row, "ir", "ar", "revenue") / 100, number(row, "iu", "au", "units")
    return number(row, "r", "revenue") / 100, number(row, "u", "units")


def each_chunk(start: date, end: date, errors: list, label: str, request):
    for chunk_start, chunk_end in year_ranges(start, end):
        try:
            yield request(chunk_start, chunk_end)
        except RuntimeError as exc:
            errors.append(f"{label} {chunk_start.year}: {exc}")


def fetch_rows(path: str, os_name: str, country: str, extra: dict, start: date, end: date, errors: list):
    request = lambda s, e: get(f"{os_name}/{path}", {
        "app_ids": ",".join(APPS[os_name]), "countries": country,
        "start_date": s.isoformat(), "end_date": e.isoformat(), **extra,
    })
    for rows in each_chunk(start, end, errors, f"{path} {os_name} {country}", request):
        yield from rows


def fetch():
    end = last_full_month_end(date.today())
    start = date.fromisoformat(START)
    app_os = {str(app_id): os_name for os_name, ids in APPS.items() for app_id in ids}
    errors = []
    # monthly[국가][YYYY-MM][앱 ID] = {"revenue", "downloads", "dau", "mau", "rank", "rankBest", "rankDays"}
    monthly = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    # daily[국가][앱 ID][지표][YYYY-MM-DD] = 값
    daily = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))

    def known(app_id, label):
        if app_id in app_os:
            return True
        errors.append(f"{label}: 알 수 없는 앱 ID {app_id!r}")
        return False

    for os_name, app_ids in APPS.items():
        if not app_ids:
            continue
        for country in COUNTRIES:
            for row in fetch_rows("sales_report_estimates", os_name, country, {"date_granularity": "monthly"}, start, end, errors):
                app_id = app_key(row)
                if known(app_id, f"monthly {country}"):
                    cell = monthly[country][day_key(row)[:7]][app_id]
                    revenue, downloads = sales_values(os_name, row)
                    cell["revenue"] = cell.get("revenue", 0) + revenue
                    cell["downloads"] = cell.get("downloads", 0) + downloads
            for row in fetch_rows("sales_report_estimates", os_name, country, {"date_granularity": "daily"}, start, end, errors):
                app_id = app_key(row)
                if known(app_id, f"daily {country}"):
                    revenue, downloads = sales_values(os_name, row)
                    daily[country][app_id]["revenue"][day_key(row)] = round(revenue)
                    daily[country][app_id]["downloads"][day_key(row)] = downloads
            # iOS는 iPhone과 iPad 사용자를 더합니다. 두 기기를 모두 쓰는 사용자는 중복될 수 있습니다.
            for row in fetch_rows("usage/active_users", os_name, country, {"time_period": "day"}, start, end, errors):
                app_id = app_key(row)
                if known(app_id, f"dau {country}"):
                    daily[country][app_id]["dau"][day_key(row)] = number(row, "users", "iphone_users", "ipad_users")
            for row in fetch_rows("usage/active_users", os_name, country, {"time_period": "month"}, start, end, errors):
                app_id = app_key(row)
                if known(app_id, f"mau {country}"):
                    monthly[country][day_key(row)[:7]][app_id]["mau"] = number(row, "users", "iphone_users", "ipad_users")

        category, chart = RANK_CHARTS[os_name]
        rank_countries = ",".join(c for c in COUNTRIES if c != "WW")
        request = lambda s, e: get(f"{os_name}/category/category_history", {
            "app_ids": ",".join(app_ids), "category": category, "chart_type_ids": chart,
            "countries": rank_countries, "start_date": s.isoformat(), "end_date": e.isoformat(),
        })
        for result in each_chunk(start, end, errors, f"rank {os_name}", request):
            for app_id, by_country in result.items():
                if app_id == "lines" or not known(str(app_id), "rank"):
                    continue
                for country, by_category in by_country.items():
                    for point in by_category.get(category, {}).get(chart, {}).get("graphData", []):
                        if point[1]:
                            day = datetime.fromtimestamp(point[0], timezone.utc).date().isoformat()
                            daily[country][str(app_id)]["rank"][day] = point[1]

    # 일 단위 DAU와 순위로 월 평균을 만듭니다. 순위는 차트에 오른 날만 평균하고 그 일수를 함께 남깁니다.
    for country, apps in daily.items():
        for app_id, metrics in apps.items():
            by_month = defaultdict(lambda: defaultdict(list))
            for metric in ("dau", "rank"):
                for day, value in metrics.get(metric, {}).items():
                    by_month[day[:7]][metric].append(value)
            for month, values in by_month.items():
                cell = monthly[country][month][app_id]
                if values["dau"]:
                    cell["dau"] = round(sum(values["dau"]) / len(values["dau"]))
                if values["rank"]:
                    cell["rank"] = round(sum(values["rank"]) / len(values["rank"]), 1)
                    cell["rankBest"] = min(values["rank"])
                    cell["rankDays"] = len(values["rank"])

    series = {}
    for country, months in monthly.items():
        series[country] = {}
        for key in sorted(months):
            apps = {app_id: {k: (round(v) if k in ("revenue", "downloads") else v) for k, v in cell.items()} for app_id, cell in months[key].items()}
            platforms = defaultdict(lambda: {"revenue": 0, "downloads": 0})
            for app_id, cell in apps.items():
                platforms[app_os[app_id]]["revenue"] += cell.get("revenue", 0)
                platforms[app_os[app_id]]["downloads"] += cell.get("downloads", 0)
            series[country][key] = {
                "revenue": sum(c.get("revenue", 0) for c in apps.values()),
                "downloads": sum(c.get("downloads", 0) for c in apps.values()),
                "platforms": dict(platforms),
                "apps": apps,
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

    # 일 단위 값은 확대 보기를 열 때만 읽도록 따로 저장합니다. 각 계열은 첫 값의 날짜 위치(o)와 그 뒤 값 배열(v)입니다.
    first_day = start.toordinal()
    daily_out = {}
    for country, apps in daily.items():
        for app_id, metrics in apps.items():
            for metric, values in metrics.items():
                if not values:
                    continue
                offsets = {date.fromisoformat(day).toordinal() - first_day: value for day, value in values.items()}
                low, high = min(offsets), max(offsets)
                daily_out.setdefault(country, {}).setdefault(app_id, {})[metric] = {"o": low, "v": [offsets.get(i) for i in range(low, high + 1)]}
    DAILY_FILE.write_text("window.SENSORTOWER_DAILY=" + json.dumps({"start": start.isoformat(), "end": end.isoformat(), "series": daily_out}, separators=(",", ":")) + ";\n", encoding="utf-8")

    print(json.dumps({
        "range": data["range"],
        "months": {c: len(v) for c, v in series.items()},
        "daily": {c: {app_id: sorted(m) for app_id, m in apps.items()} for c, apps in daily_out.items()},
        "errors": errors,
    }, ensure_ascii=False, indent=2))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sensor Tower 매출·다운로드·활성 사용자·매출 순위 추정치를 sensortower-data.js와 sensortower-daily.js로 저장합니다.")
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
