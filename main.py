# -*- coding: utf-8 -*-
"""
날짜별 박스오피스(KOBIS 영화진흥위원회 오픈API) 스트림릿 앱
------------------------------------------------------------
달력에서 날짜를 골라 그날의 박스오피스를 볼 수 있습니다.
(단, 오늘 데이터는 아직 집계 전이라 고를 수 있는 가장 늦은 날짜는 '어제'까지입니다)
초보자를 위해 각 부분에 한국어 주석을 달아두었습니다.
"""

import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------
# 1. 기본 설정
# ------------------------------------------------------------
# 페이지 제목, 아이콘 등 화면 기본 설정을 해줍니다.
st.set_page_config(page_title="어제의 박스오피스", page_icon="🎬", layout="wide")

# KOBIS 오픈API 주소 (공식 문서에 나온 그대로)
API_URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"


# ------------------------------------------------------------
# 2. '어제(한국 시간 기준)' 날짜 계산하기
# ------------------------------------------------------------
def get_yesterday_kst_date():
    """
    배포 서버의 시계가 한국 시간이 아닐 수 있으므로,
    UTC 기준 현재 시각을 구한 뒤 한국 시간(UTC+9)으로 직접 변환합니다.
    그런 다음 하루를 빼서 '어제' 날짜를 date 객체로 돌려줍니다.
    (달력에서 고를 수 있는 가장 늦은 날짜를 정할 때 사용합니다)
    """
    kst = timezone(timedelta(hours=9))  # 한국 표준시(UTC+9) 정의
    now_kst = datetime.now(timezone.utc).astimezone(kst)  # 지금 시각을 한국 시간으로 변환
    yesterday_kst = now_kst - timedelta(days=1)  # 하루 전 날짜
    return yesterday_kst.date()


def to_target_dt(selected_date) -> str:
    """
    달력에서 고른 date 객체를 KOBIS API가 원하는 yyyymmdd 형식(8자리 문자열)로 바꿔줍니다.
    """
    return selected_date.strftime("%Y%m%d")


# ------------------------------------------------------------
# 3. API 호출 함수 (결과를 1시간 동안 기억(캐시)해서 재호출 방지)
# ------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="박스오피스 정보를 불러오는 중...")
def fetch_box_office(target_dt: str, api_key: str):
    """
    KOBIS API를 호출해서 원본 응답(JSON)을 그대로 돌려주는 함수입니다.
    같은 target_dt로 다시 호출하면, 1시간(3600초) 안에는
    실제 요청을 보내지 않고 캐시된 결과를 그대로 재사용합니다.

    반환값: (성공여부, 데이터 또는 에러메시지)
    """
    params = {
        "key": api_key,
        "targetDt": target_dt,
    }

    try:
        # timeout을 걸어서 응답이 너무 오래 걸리면 예외가 나도록 합니다.
        response = requests.get(API_URL, params=params, timeout=10)
    except requests.exceptions.RequestException as e:
        # 인터넷 연결 문제, 타임아웃 등 요청 자체가 실패한 경우
        return False, f"요청 실패: 인터넷 연결 상태나 KOBIS 서버 상태를 확인해 주세요. (상세: {e})"

    # 상태 코드가 200이 아니면 서버 쪽 문제일 가능성이 큽니다.
    if response.status_code != 200:
        return False, f"요청 실패: 서버가 상태코드 {response.status_code}를 반환했습니다. 잠시 후 다시 시도해 주세요."

    try:
        data = response.json()
    except ValueError:
        return False, "요청 실패: 서버 응답을 JSON으로 해석할 수 없습니다. API 주소나 파라미터를 확인해 주세요."

    # 문서에 나온 대로, 인증키가 틀려도 상태코드는 200이고 대신 faultInfo가 옵니다.
    if "faultInfo" in data:
        fault = data["faultInfo"]
        message = fault.get("message", "알 수 없는 오류")
        return False, (
            "인증키 오류로 보입니다: "
            f"'{message}'. secrets.toml(또는 Streamlit Cloud의 Secrets)에 등록한 "
            "KOBIS_KEY 값이 정확한지 확인해 주세요."
        )

    # 정상 구조인지 확인 (boxOfficeResult가 없으면 예상과 다른 응답)
    if "boxOfficeResult" not in data:
        return False, "요청 실패: 응답 구조가 예상과 다릅니다. KOBIS API 문서가 변경되었는지 확인해 주세요."

    return True, data["boxOfficeResult"]


# ------------------------------------------------------------
# 4. 문자열로 온 숫자를 진짜 숫자(int)로 바꿔주는 함수
# ------------------------------------------------------------
def to_dataframe(daily_list):
    """
    API가 돌려주는 dailyBoxOfficeList(딕셔너리 목록)를
    pandas DataFrame으로 바꾸면서, 숫자 컬럼들을 문자열 -> 정수로 변환합니다.
    """
    df = pd.DataFrame(daily_list)

    # 정렬/그래프에 쓸 숫자 컬럼들을 int로 변환합니다.
    numeric_cols = ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "rankInten"]
    for col in numeric_cols:
        if col in df.columns:
            # errors="coerce": 혹시 이상한 값이 있어도 앱이 죽지 않고 NaN 처리 후 넘어감
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ------------------------------------------------------------
# 5. 화면 그리기 시작
# ------------------------------------------------------------
st.title("🎬 날짜별 박스오피스")

# 인증키는 절대 코드에 직접 쓰지 않고, Streamlit의 secrets 금고에서 불러옵니다.
# Streamlit Cloud에 배포할 때는 앱 설정(Settings) > Secrets 메뉴에
# 아래처럼 등록해두면 됩니다.
#   KOBIS_KEY = "발급받은_인증키"
if "KOBIS_KEY" not in st.secrets:
    st.error(
        "KOBIS_KEY가 설정되어 있지 않습니다. "
        "Streamlit Cloud의 'Settings > Secrets'에 KOBIS_KEY를 등록해 주세요."
    )
    st.stop()  # 인증키가 없으면 더 진행하지 않고 여기서 멈춤

api_key = st.secrets["KOBIS_KEY"]

# 달력에서 날짜를 고르는 위젯입니다.
# 오늘 데이터는 아직 집계 전이므로, 고를 수 있는 가장 늦은 날짜는 '어제(한국시간)'로 제한합니다.
yesterday_kst_date = get_yesterday_kst_date()
selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday_kst_date,       # 처음 화면에 보여줄 기본값: 어제
    max_value=yesterday_kst_date,   # 오늘/미래 날짜는 선택 불가
)

target_dt = to_target_dt(selected_date)
target_dt_display = selected_date.strftime("%Y-%m-%d")
st.caption(f"조회 기준일: {target_dt_display}")

# API 호출 (캐시 덕분에 같은 날짜면 1시간 동안 재호출 안 함)
success, result = fetch_box_office(target_dt, api_key)

# ------------------------------------------------------------
# 6. 실패했을 때 안내 메시지 보여주기
# ------------------------------------------------------------
if not success:
    st.error(result)  # result에 이미 한국어 안내 메시지가 들어있습니다.
    st.stop()

daily_list = result.get("dailyBoxOfficeList", [])

if not daily_list:
    st.warning(f"{target_dt_display}, 그날은 아직 집계 전입니다. 다른 날짜를 선택해 주세요.")
    st.stop()

# ------------------------------------------------------------
# 7. 데이터 정리 (문자열 숫자 -> 진짜 숫자)
# ------------------------------------------------------------
df = to_dataframe(daily_list)
df = df.sort_values("rank")  # 순위 기준으로 정렬

# ------------------------------------------------------------
# 8. 1위 영화 - 지표 카드 3장
# ------------------------------------------------------------
st.subheader("🏆 1위 영화")

top1 = df.iloc[0]

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label=f"{top1['movieNm']} (오늘 관객수)", value=f"{int(top1['audiCnt']):,}명")
with col2:
    st.metric(label="누적 관객수", value=f"{int(top1['audiAcc']):,}명")
with col3:
    st.metric(label="스크린수", value=f"{int(top1['scrnCnt']):,}개")

st.caption(f"개봉일: {top1['openDt']}  |  전날 대비 순위 변동: {top1['rankInten']}")

st.divider()

# ------------------------------------------------------------
# 9. 관객수 상위 5편 - 막대그래프
# ------------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = df.sort_values("audiCnt", ascending=False).head(5)

# 막대그래프는 영화명을 인덱스로, 관객수를 값으로 사용합니다.
chart_data = top5.set_index("movieNm")["audiCnt"]
st.bar_chart(chart_data)

st.divider()

# ------------------------------------------------------------
# 10. 전체 표
# ------------------------------------------------------------
st.subheader("📋 전체 박스오피스 순위")

table_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt", "rankInten"]].copy()


def format_rank_change(value) -> str:
    """
    rankInten(전날 대비 순위 증감)을 화살표 글자로 바꿔줍니다.
    문서 기준: 양수면 순위가 오른 것 -> 빨간 위 화살표, 음수면 내린 것 -> 파란 아래 화살표.
    (0이거나 값이 없으면 순위 변동 없음으로 표시)
    """
    if pd.isna(value) or int(value) == 0:
        return "－"
    if value > 0:
        return f"▲{int(value)}"  # 순위 상승
    return f"▼{abs(int(value))}"  # 순위 하락


def format_movie_name(row) -> str:
    """
    누적관객(audiAcc)이 100만 명을 넘으면 영화명 옆에 트로피 이모지를 붙여줍니다.
    """
    name = row["movieNm"]
    if pd.notna(row["audiAcc"]) and row["audiAcc"] >= 1_000_000:
        return f"{name} 🏆"
    return name


table_df["순위변동"] = table_df["rankInten"].apply(format_rank_change)
table_df["영화명"] = table_df.apply(format_movie_name, axis=1)

table_df = table_df[["rank", "영화명", "openDt", "audiCnt", "audiAcc", "scrnCnt", "순위변동"]]
table_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수", "순위변동"]


def color_rank_change(value: str) -> str:
    """
    순위변동 글자 색을 정해줍니다: ▲(상승)는 빨간색, ▼(하락)는 파란색.
    """
    if isinstance(value, str) and value.startswith("▲"):
        return "color: red; font-weight: bold;"
    if isinstance(value, str) and value.startswith("▼"):
        return "color: blue; font-weight: bold;"
    return ""


# 숫자 컬럼은 천 단위 콤마를 넣고, 순위변동 컬럼은 색을 입혀서 보여줍니다.
# st.dataframe은 셀마다 다른 글자색을 지정할 수 없어서, 여기서는 pandas Styler로
# HTML 표를 만든 뒤 st.markdown으로 그려줍니다.
styler = table_df.style.format(
    {"관객수": "{:,.0f}", "누적관객": "{:,.0f}", "스크린수": "{:,.0f}"}
)

# pandas 2.1 이상에서는 Styler.map, 그보다 낮은 버전에서는 Styler.applymap을 사용합니다.
if hasattr(styler, "map"):
    styler = styler.map(color_rank_change, subset=["순위변동"])
else:
    styler = styler.applymap(color_rank_change, subset=["순위변동"])

styled_table = styler.hide(axis="index").set_table_styles(
    [
        {"selector": "th", "props": "text-align: center; padding: 6px 10px;"},
        {"selector": "td", "props": "padding: 6px 10px;"},
    ]
)

st.markdown(styled_table.to_html(), unsafe_allow_html=True)
