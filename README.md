# Blue Archive Research Data

블루 아카이브의 콜라보, 굿즈, 피규어 출시 데이터를 정리한 정적 리서치 사이트입니다.

## 페이지

`index.html`은 전체 메뉴입니다.

`goods-catalog.html`은 Yostar와 Animate 상품 카탈로그입니다. 상품 검색, 판매처, 카테고리, 판매 연도, 가격, 정렬 필터를 제공합니다.

`blue-archive-goods-trend.html`은 일반 굿즈의 월별 또는 분기별 출시 추이와 카테고리 구성을 보여줍니다. 피규어는 제외합니다.

`blue-archive-figure-atlas.html`은 피규어 유형별 출시 흐름을 보여줍니다.

`blue-archive-collaboration-atlas.html`은 오프라인 및 공공기관 콜라보를 포함한 콜라보 시계열입니다.

`blue-archive-goods-atlas.html`은 굿즈 관련 보조 시각화입니다.

## 데이터 원본

업데이트 기준은 Excel 파일이 아니라 크롤러가 생성한 `progress.json`입니다.

Yostar 원본:

`<LOCAL_PATH>`

Yostar 이미지:

`<LOCAL_PATH>`

Animate 원본:

`<LOCAL_PATH>`

Animate 이미지:

`<LOCAL_PATH>`

Yostar는 판매 시작일을 사용하고, Animate는 발매일을 사용합니다. 두 날짜의 의미가 다르므로 시계열 해석 때 구분해야 합니다.

## 갱신 방법

먼저 두 크롤러를 실행해 `progress.json`과 `images`를 최신 상태로 둡니다. 그 다음 프로젝트 폴더에서 아래 명령을 실행합니다.

```powershell
& "<LOCAL_PATH>" update_catalog.py
```

스크립트가 수행하는 작업은 다음과 같습니다.

두 progress.json 통합
상품 URL 기준 중복 제거
Yostar와 Animate 이미지 연결
이미지를 catalog-images 폴더의 WebP 썸네일로 변환
상품명, 가격, 판매 상태를 한국어 표기로 정리
피규어 여부와 판매 월 계산
catalog-data.js 생성
catalog-build-report.json 생성

업데이트 결과는 `catalog-build-report.json`에서 확인합니다. 현재 2026년 10월 1일 갱신본은 전체 상품 3,635건, 이미지 연결 3,633건, 이미지 누락 2건입니다. 누락 상품은 Yostar 4858번과 4859번이며 원본 이미지 경로가 없습니다.

## 데이터 표시 기준

상품 수는 판매량이 아니라 상품 행 또는 SKU 수입니다.

일반 굿즈 추이에서는 피규어 상품을 제외합니다.

날짜가 없는 상품은 월별 및 분기별 추이 계산에서 제외합니다. 카탈로그에는 남아 있을 수 있습니다.

가격이 없는 상품은 `가격 미정`으로 표시합니다.

원본에 없는 날짜, 가격, 이벤트명은 임의로 추가하지 않습니다.

## 배포

서버가 필요 없는 정적 HTML 사이트입니다. 프로젝트 전체를 GitHub 저장소에 올리고 GitHub Pages를 연결하면 됩니다.

```powershell
git add .
git commit -m "Update research data"
git push
```

`catalog-data.js`와 `catalog-images`는 카탈로그 페이지에 필요한 핵심 파일이므로 함께 커밋해야 합니다.
