# -*- coding: utf-8 -*-
"""
영화 데이터 그래프 도감 1 - 시간
------------------------------------------------------------
KOBIS 일별 박스오피스 1년치(365일, 10위권) 데이터를 가지고
'시간'을 축으로 하는 그래프들을 모아두는 도감 앱입니다.

앞으로 그래프를 계속 추가할 예정이라, 화면을 '구역(section)'
단위로 나눠두었습니다. 새 그래프를 추가할 때는 이 파일 아래쪽의
"# ▶▶▶ 여기부터 새 구역을 추가하세요 ◀◀◀" 안내를 참고하세요.

초보자를 위해 각 부분에 한국어 주석을 달아두었습니다.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

# ------------------------------------------------------------
# 0. 기본 설정
# ------------------------------------------------------------
st.set_page_config(page_title="영화 데이터 그래프 도감 1 - 시간", page_icon="📈", layout="wide")

# 데이터가 올라와 있는 원본 주소입니다.
DATA_URL = "https://raw.githubusercontent.com/greatsong/modudata/main/data/kobis_daily.csv"


# ------------------------------------------------------------
# 1. 데이터 불러오기 + 전처리 (1시간 동안 캐시해서 재다운로드 방지)
# ------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner="박스오피스 1년치 데이터를 불러오는 중...")
def load_data():
    """
    CSV를 읽어와서 pandas DataFrame으로 돌려줍니다.
    성공하면 (True, DataFrame), 실패하면 (False, 에러메시지)를 돌려줍니다.
    """
    try:
        df = pd.read_csv(DATA_URL)
    except Exception as e:  # 네트워크 오류, 서버 오류 등 모든 예외를 잡습니다.
        return False, f"데이터를 불러오지 못했습니다. 인터넷 연결이나 주소를 확인해 주세요. (상세: {e})"

    if df.empty:
        return False, "데이터가 비어 있습니다. 원본 CSV 파일을 확인해 주세요."

    # 컬럼 이름이 기대한 것과 다르면(문서가 바뀌었을 수 있으니) 안내합니다.
    expected_cols = {"날짜", "순위", "영화코드", "영화명", "일관객", "누적관객", "스크린수", "상영횟수"}
    if not expected_cols.issubset(set(df.columns)):
        return False, (
            "예상한 컬럼(날짜·순위·영화코드·영화명·일관객·누적관객·스크린수·상영횟수)이 "
            "보이지 않습니다. 원본 CSV의 구조가 바뀌었는지 확인해 주세요."
        )

    # 날짜 열(하이픈 없는 8자리 숫자, 예: 20250901)을 진짜 날짜(datetime) 타입으로 바꿔줍니다.
    df["날짜"] = pd.to_datetime(df["날짜"].astype(str), format="%Y%m%d")

    # 숫자로 다뤄야 할 컬럼들을 숫자 타입으로 확실하게 바꿔줍니다.
    numeric_cols = ["순위", "일관객", "누적관객", "스크린수", "상영횟수"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return True, df


# ------------------------------------------------------------
# 2. 화면 그리기 시작
# ------------------------------------------------------------
st.title("📈 영화 데이터 그래프 도감 1 - 시간")
st.caption("KOBIS 일별 박스오피스 1년치 데이터로, '시간'에 따른 변화를 살펴보는 그래프 모음입니다.")

success, result = load_data()

if not success:
    st.error(result)
    st.stop()

df = result

st.divider()

# ==============================================================
# [구역 1] 영화별 일관객 변화 추이
# ==============================================================
st.header("1️⃣ 영화별 일별 관객수 변화 추이")

# 영화명을 가나다순으로 정렬해서 드롭다운 목록을 만듭니다.
movie_list = sorted(df["영화명"].dropna().unique())

selected_movie = st.selectbox(
    "영화를 선택하세요",
    movie_list,
    key="section1_movie_select",
)

# 선택한 영화의 기록만 골라내고, 날짜순으로 정렬합니다.
movie_df = df[df["영화명"] == selected_movie].sort_values("날짜")

if movie_df.empty:
    st.warning("선택한 영화의 데이터가 없습니다.")
else:
    fig = px.line(
        movie_df,
        x="날짜",
        y="일관객",
        markers=True,  # 각 날짜마다 점을 찍어서 마우스를 올리기 쉽게 해줍니다.
        title=f"'{selected_movie}'의 날짜별 일일 관객수",
        labels={"날짜": "날짜", "일관객": "일일 관객수(명)"},
    )
    # 마우스를 올렸을 때 날짜와 관객수가 보기 좋게 나오도록 설정합니다.
    fig.update_traces(
        hovertemplate="날짜: %{x|%Y-%m-%d}<br>관객수: %{y:,}명<extra></extra>"
    )
    fig.update_layout(hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)

# 그래프 아래에, 이 그래프에서 무엇을 알 수 있는지 한 문장으로 적어둘 자리입니다.
# (직접 문구를 채워 넣거나, 필요하면 st.markdown(...)으로 고정 문구로 바꿔도 됩니다.)
st.text_input(
    "💡 이 그래프로 알 수 있는 것",
    value="",
    placeholder="예: 개봉 첫 주에 관객수가 급증했다가 시간이 지나며 점차 줄어드는 흐름을 보인다.",
    key="section1_insight",
)

st.divider()

# ==============================================================
# ▶▶▶ 여기부터 새 구역을 추가하세요 ◀◀◀
# 다음 그래프를 만들 때는 아래 형식을 그대로 복사해서 쓰면 됩니다.
#
# st.header("2️⃣ (새 그래프 제목)")
# ... 그래프를 그리는 코드 ...
# st.text_input("💡 이 그래프로 알 수 있는 것", value="", placeholder="...", key="section2_insight")
# st.divider()
# ==============================================================
