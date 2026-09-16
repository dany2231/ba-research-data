from __future__ import annotations

import json
import re
import sys
import runpy
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


PROJECT = Path(__file__).resolve().parent
YOSTAR = Path(r"C:\Users\daniel2231\OneDrive - NCSOFT\문서\업무\아스트라에 오라티오\yostar-crawl")
ANIMATE = Path(r"C:\Users\daniel2231\OneDrive - NCSOFT\문서\업무\아스트라에 오라티오\animate-crawl")
DATA_FILE = PROJECT / "catalog-data.js"
IMAGE_DIR = PROJECT / "catalog-images"
REPORT_FILE = PROJECT / "catalog-build-report.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_current():
    raw = DATA_FILE.read_text(encoding="utf-8")
    prefix = "window.CATALOG_PRODUCTS="
    if not raw.startswith(prefix):
        raise ValueError("catalog-data.js 형식을 확인해 주세요.")
    return json.loads(raw[len(prefix):].rstrip().removesuffix(";"))


def text(value):
    return "" if value is None else str(value).strip()


def site_id(url: str):
    match = re.search(r"/(?:pd|detail)/(\d+)", url)
    return match.group(1) if match else ""


def price_number(value):
    digits = re.sub(r"[^0-9]", "", text(value))
    value = int(digits) if digits else None
    return value if value and value > 0 else None


def price_label(value):
    return f"{value:,}엔(부가세 포함)" if value is not None else "가격 미정"


def normalize_status(value):
    value = text(value)
    mapping = {
        "販売終了": "판매 종료",
        "この商品の販売は終了しました": "판매 종료",
        "이 상품의 판매가 종료되었습니다": "판매 종료",
        "판매중": "판매 중",
        "カートに入れる": "판매 중",
        "주문": "판매 중",
        "予約受付中": "예약 접수 중",
        "지금 품절 중입니다.": "품절",
        "残りわずか": "재고 얼마 남지 않음",
        "남은": "재고 얼마 남지 않음",
        "在庫あり": "재고 있음",
        "取り寄せ": "입고 예정",
        "通常1～2日以内に入荷": "통상 1~2일 내 입고",
        "통상 1~2일 이내에 입하": "통상 1~2일 내 입고",
        "通常2～5日以内に入荷": "통상 2~5일 내 입고",
        "통상 2~5일 이내에 입하": "통상 2~5일 내 입고",
        "発売日以降出荷": "발매일 이후 출하",
        "곧 판매 개시": "판매 예정",
    }
    return mapping.get(value, value or "미상")


def month(value):
    match = re.search(r"(20\d{2})[./-](\d{1,2})", text(value))
    return f"{match.group(1)}-{int(match.group(2)):02d}" if match else ""


def is_figure(name: str, category: str):
    value = f"{name} {category}".lower()
    return any(k in value for k in ("피규어", "피겨", "figma", "넨도로이드", "봉제", "인형", "figure"))


def normalize_category(name: str, raw: str):
    value = f"{name} {raw}".lower()
    rules = (
        (("피규어", "피겨", "figma", "넨도로이드", "봉제", "인형"), "피규어・봉제인형"),
        (("아크릴", "캔 배지", "캔뱃지", "키홀더", "열쇠 고리"), "캔 배지 아크릴 제품"),
        (("태피스트리", "포스터"), "태피스트리 포스터"),
        (("브로마이드", "앨범", "포토카드"), "브로마이드 앨범"),
        (("다키마쿠라", "쿠션", "베개", "침구", "인테리어"), "다키마 쿠라 커버 인테리어"),
        (("티셔츠", "셔츠", "파카", "후드", "의류", "액세서리", "가방", "파우치", "모자"), "의류 액세서리"),
        (("수건", "손수건"), "수건 손수건"),
        (("서적", "책", "코믹", "잡지", "일러스트집", "설정집"), "서적 · 일러스트 모음"),
        (("cd", "dvd", "blu-ray", "블루레이", "음악", "영상", "미디어"), "영상, 음악, 미디어"),
        (("텀블러", "컵", "머그", "접시", "식기", "주방"), "주방용품・칼집"),
        (("볼펜", "노트", "파일", "스티커", "문구", "책상", "메모"), "문구・책상용품"),
        (("케이블", "충전", "배터리", "이어폰", "전자", "가젯"), "가젯"),
        (("과자", "음료", "식품", "캔디", "초콜릿"), "음식/음료"),
    )
    for keys, category in rules:
        if any(key in value for key in keys):
            return category
    return "기타"


def thumb(source: Path, target: Path):
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((480, 480), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (480, 480), "white")
        canvas.paste(image, ((480 - image.width) // 2, (480 - image.height) // 2))
        canvas.save(target, "WEBP", quality=76, method=6)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    current = load_current()
    current_by_url = {p.get("url", ""): p for p in current if p.get("url")}
    max_animate_id = max((int(m.group(1)) for p in current if (m := re.fullmatch(r"AN-(\d+)", p.get("id", "")))), default=0)
    next_animate_id = max_animate_id + 1
    products = []
    missing = []
    IMAGE_DIR.mkdir(exist_ok=True)

    for source, root in (("Yostar", YOSTAR), ("Animate", ANIMATE)):
        rows = load_json(root / "progress.json")
        for row_number, row in enumerate(rows, start=1):
            url = text(row.get("url"))
            old = current_by_url.get(url, {})
            if source == "Yostar":
                product_id = text(row.get("product_id"))
                name = text(row.get("name_ko"))
                price_text = text(row.get("price_ko"))
                start = text(row.get("sale_start"))
                end = text(row.get("sale_end"))
                category = text(row.get("category")) or old.get("category") or "미분류"
                if category == "음식 · 음료":
                    category = "음식/음료"
                event = text(row.get("event"))
                status = text(row.get("sale_status")) or "미상"
                lookup_id = product_id
                prefix = "y"
            else:
                found_id = old.get("id")
                if not found_id:
                    found_id = f"AN-{next_animate_id}"
                    next_animate_id += 1
                product_id = found_id
                name = text(row.get("name"))
                price_text = text(row.get("price"))
                start = text(row.get("release_date"))
                end = ""
                category = old.get("category") or normalize_category(name, text(row.get("category")))
                event = old.get("event", "")
                status = text(row.get("status")) or "미상"
                lookup_id = site_id(url)
                prefix = "a"

            source_image = root / text(row.get("imageFile"))
            image_name = f"{prefix}_{lookup_id}.webp" if lookup_id and source_image.is_file() else ""
            if image_name:
                try:
                    thumb(source_image, IMAGE_DIR / image_name)
                except Exception as exc:
                    missing.append({"source": source, "id": product_id, "reason": f"image error: {exc}"})
                    image_name = ""
            else:
                missing.append({"source": source, "id": product_id, "reason": "not found"})

            numeric_price = price_number(price_text)
            products.append({
                "source": source,
                "id": product_id,
                "name": name,
                "priceText": price_label(numeric_price),
                "price": numeric_price,
                "start": start,
                "end": end,
                "category": category,
                "url": url,
                "event": event,
                "status": normalize_status(status),
                "month": month(start),
                "figure": is_figure(name, category),
                "image": f"catalog-images/{image_name}" if image_name else "",
            })

    unique = {}
    for product in products:
        key = product["url"] or f'{product["source"]}:{product["id"]}'
        unique[key] = product
    products = list(unique.values())
    DATA_FILE.write_text("window.CATALOG_PRODUCTS=" + json.dumps(products, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")

    source_counts = Counter(p["source"] for p in products)
    category_counts = Counter(p["category"] for p in products)
    report = {
        "rows": len(products),
        "matched_images": sum(bool(p["image"]) for p in products),
        "missing_images": len(missing),
        "sources": dict(source_counts),
        "categories": dict(category_counts),
        "thumbnail_bytes": sum(p.stat().st_size for p in IMAGE_DIR.glob("*.webp")),
        "missing_sample": missing[:30],
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    translator = Path(r"C:\Users\daniel2231\Documents\Codex\2026-08-19\referenced-chatgpt-conversation-this-is-an\work\translate_catalog_names.py")
    if translator.exists():
        runpy.run_path(str(translator))


if __name__ == "__main__":
    main()
