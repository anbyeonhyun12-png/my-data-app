import requests
import streamlit as st
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo


# --------------------------------------------------
# 기본 설정
# --------------------------------------------------

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide",
)

# KOBIS 일일 박스오피스 API 주소
KOBIS_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# --------------------------------------------------
# 한국 시간 기준 날짜 계산
# --------------------------------------------------

def get_korea_today():
    """현재 날짜를 한국 시간 기준으로 가져옵니다."""
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


# 오늘 날짜
today_kst = get_korea_today()

# 오늘은 아직 집계 전이므로 선택 가능한 가장 늦은 날짜는 어제입니다.
latest_available_date = today_kst - timedelta(days=1)


# --------------------------------------------------
# 날짜를 KOBIS API용 문자열로 변환
# --------------------------------------------------

def format_target_date(selected_date):
    """날짜를 KOBIS가 요구하는 yyyymmdd 형식으로 변환합니다."""
    return selected_date.strftime("%Y%m%d")


# --------------------------------------------------
# KOBIS API 호출
# --------------------------------------------------

@st.cache_data(ttl=3600)
def get_box_office(target_date):
    """
    KOBIS API에서 해당 날짜의 일일 박스오피스를 가져옵니다.

    같은 날짜를 다시 조회하면 약 1시간 동안 캐시된 결과를 사용합니다.
    """

    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키는 코드에 작성하지 않습니다.
    api_key = st.secrets["KOBIS_KEY"]

    params = {
        "key": api_key,
        "targetDt": target_date,
    }

    try:
        response = requests.get(
            KOBIS_URL,
            params=params,
            timeout=10,
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

        data = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "empty": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                f"오류 내용: {e}\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• 인터넷 연결 상태\n"
                "• KOBIS API 서버 상태\n"
                "• API 주소가 올바른지"
            ),
        }

    except ValueError:
        return {
            "ok": False,
            "empty": False,
            "message": (
                "KOBIS API에서 정상적인 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API 서버 상태를 확인해 주세요."
            ),
        }

    # --------------------------------------------------
    # 인증키 오류 확인
    # --------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있으므로
    # 반드시 faultInfo가 있는지 확인합니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        fault_message = (
            fault_info.get("message")
            or fault_info.get("faultMessage")
            or fault_info.get("errorMessage")
            or str(fault_info)
        )

        return {
            "ok": False,
            "empty": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 내용: {fault_message}\n\n"
                "다음 사항을 확인해 주세요.\n"
                "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 있는지\n"
                "• KOBIS_KEY에 발급받은 인증키를 정확히 넣었는지\n"
                "• KOBIS API 이용이 정상적으로 가능한지"
            ),
        }

    # 예상한 응답 구조가 없는 경우
    if "boxOfficeResult" not in data:
        return {
            "ok": False,
            "empty": False,
            "message": (
                "KOBIS API 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API 서버 상태와 응답 형식을 확인해 주세요."
            ),
        }

    box_office_result = data["boxOfficeResult"]

    # 영화 목록 가져오기
    movies = box_office_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있으면 '아직 집계 전'으로 안내합니다.
    if not movies:
        return {
            "ok": True,
            "empty": True,
            "message": "그날은 아직 집계 전입니다.",
        }

    return {
        "ok": True,
        "empty": False,
        "movies": movies,
    }


# --------------------------------------------------
# 문자열 숫자를 정수로 변환
# --------------------------------------------------

def to_int(value):
    """
    KOBIS API의 숫자 문자열을 정수로 변환합니다.

    예:
    '12,345' -> 12345
    '12345'  -> 12345
    """

    if value is None:
        return 0

    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


# --------------------------------------------------
# 화면 제목
# --------------------------------------------------

st.title("🎬 박스오피스 조회")

st.caption(
    "한국 시간 기준으로 조회할 날짜를 선택하세요. "
    "오늘은 아직 집계 전이므로 선택할 수 없습니다."
)


# --------------------------------------------------
# 날짜 선택
# --------------------------------------------------

selected_date = st.date_input(
    "조회 날짜",
    value=latest_available_date,
    max_value=latest_available_date,
    format="YYYY-MM-DD",
)

target_date = format_target_date(selected_date)

display_date = selected_date.strftime("%Y년 %m월 %d일")

st.caption(f"KOBIS 일일 박스오피스 · {display_date}")


# --------------------------------------------------
# API에서 데이터 가져오기
# --------------------------------------------------

result = get_box_office(target_date)


# --------------------------------------------------
# API 오류 처리
# --------------------------------------------------

if not result["ok"]:
    st.error(result["message"])
    st.stop()


# --------------------------------------------------
# 영화 목록이 비어 있는 경우
# --------------------------------------------------

if result["empty"]:
    st.info("📅 그날은 아직 집계 전입니다.")
    st.stop()


movies = result["movies"]


# --------------------------------------------------
# API 데이터를 화면에 사용하기 편하게 변환
# --------------------------------------------------

rows = []

for movie in movies:

    # 전날 대비 순위 증감
    rank_inten = to_int(movie.get("rankInten"))

    # 누적관객수
    audience_acc = to_int(movie.get("audiAcc"))

    # 누적관객이 100만 명을 넘었으면 트로피 표시
    trophy = " 🏆" if audience_acc > 1_000_000 else ""

    # 순위 변화 표시
    if rank_inten > 0:
        rank_change = f"🔺 {rank_inten}"
    elif rank_inten < 0:
        rank_change = f"🔻 {abs(rank_inten)}"
    else:
        rank_change = "-"

    rows.append(
        {
            "순위": to_int(movie.get("rank")),
            "순위변동": rank_change,
            "영화명": movie.get("movieNm", "") + trophy,
            "개봉일": movie.get("openDt", ""),
            "관객수": to_int(movie.get("audiCnt")),
            "누적관객": audience_acc,
            "스크린수": to_int(movie.get("scrnCnt")),
        }
    )


# 혹시 변환 후 데이터가 없다면 안내
if not rows:
    st.info("📅 그날은 아직 집계 전입니다.")
    st.stop()


# --------------------------------------------------
# 1위 영화
# --------------------------------------------------

first_movie = rows[0]

st.subheader(f"🏆 1위 · {first_movie['영화명']}")


# 지표 카드 3개
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "관객수",
        f"{first_movie['관객수']:,}명",
    )

with col2:
    st.metric(
        "누적관객",
        f"{first_movie['누적관객']:,}명",
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['스크린수']:,}개",
    )


# --------------------------------------------------
# 관객수 상위 5편
# --------------------------------------------------

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬합니다.
top_5 = sorted(
    rows,
    key=lambda movie: movie["관객수"],
    reverse=True,
)[:5]


# 막대그래프에 사용할 데이터
chart_data = {
    movie["영화명"]: movie["관객수"]
    for movie in top_5
}

st.bar_chart(chart_data)


# --------------------------------------------------
# 전체 박스오피스 표
# --------------------------------------------------

st.subheader("🎞️ 전체 박스오피스")

st.dataframe(
    rows,
    use_container_width=True,
    hide_index=True,
    column_config={
        "순위": st.column_config.NumberColumn(
            "순위",
            format="%d위",
        ),
        "순위변동": st.column_config.TextColumn(
            "전날 대비",
        ),
        "영화명": st.column_config.TextColumn(
            "영화명",
        ),
        "개봉일": st.column_config.TextColumn(
            "개봉일",
        ),
        "관객수": st.column_config.NumberColumn(
            "관객수",
            format="%d명",
        ),
        "누적관객": st.column_config.NumberColumn(
            "누적관객",
            format="%d명",
        ),
        "스크린수": st.column_config.NumberColumn(
            "스크린수",
            format="%d개",
        ),
    },
)
