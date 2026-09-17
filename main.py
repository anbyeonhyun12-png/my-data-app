import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# 페이지 기본 설정
st.set_page_config(page_title="어제 박스오피스", layout="wide")

# 1. 한국 시간 기준으로 '어제' 날짜 계산하기
# 배포 서버의 시계가 해외 기준이더라도 한국 시간(KST)으로 정확히 계산합니다.
tz_kst = pytz.timezone('Asia/Seoul')
now_kst = datetime.now(tz_kst)
yesterday_kst = now_kst - timedelta(days=1)
target_date = yesterday_kst.strftime('%Y%m%d')
display_date = yesterday_kst.strftime('%Y년 %m월 %d일')

st.title(f"🎬 {display_date} 박스오피스 상황판")
st.caption("영화진흥위원회(KOBIS) API 데이터를 기반으로 제공됩니다.")

# 2. API 호출 결과를 1시간(3600초) 동안 기억(캐싱)하는 함수
# 같은 날짜로 다시 요청하면 API를 중복 호출하지 않고 저장된 데이터를 씁니다.
@st.cache_data(ttl=3600)
def fetch_box_office(date):
    # 스트림릿 클라우드의 비밀 금고(Secrets)에서 API 키를 안전하게 가져옵니다.
    if "KOBIS_KEY" not in st.secrets:
        return {"error": "secrets_missing"}
        
    api_key = st.secrets["KOBIS_KEY"]
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {"key": api_key, "targetDt": date}
    
    try:
        response = requests.get(url, timeout=10)
        # HTTP 응답코드가 200이 아니면 예외를 발생시킵니다.
        response.raise_for_status() 
        return response.json()
    except requests.exceptions.RequestException:
        return {"error": "network_error"}

# 데이터 가져오기 실행
data = fetch_box_office(target_date)

# 3. 에러 처리 및 문제 확인 안내 메시지
if "error" in data:
    st.error("🚨 데이터를 불러오지 못했습니다.")
    if data["error"] == "secrets_missing":
        st.info("💡 **확인 방법:** Streamlit Cloud 설정의 **Secrets** 메뉴에 `KOBIS_KEY = \"발급받은키\"` 형태로 인증키가 등록되어 있는지 확인해 주세요.")
    else:
        st.info("💡 **확인 방법:** 영화진흥위원회 서버 또는 네트워크 상태가 불안정할 수 있습니다. 잠시 후 페이지를 새로고침(F5)해 보세요.")
        
elif "faultInfo" in data:
    # API 키가 틀렸거나 문제가 있을 때 발생하는 오류 처리
    st.error("🚨 API 인증 요류가 발생했습니다.")
    st.markdown(f"**오류 메시지:** `{data['faultInfo'].get('message', '알 수 없는 오류')}`")
    st.info("💡 **확인 방법:** 발급받은 영화진흥위원회 API 인증키가 유효한지, Streamlit Secrets에 공백 없이 정확히 입력되었는지 확인해 주세요.")

elif not data.get("boxOfficeResult", {}).get("dailyBoxOfficeList"):
    # 응답은 성공했으나 데이터 목록이 비어 있는 경우
    st.warning("⚠️ 어제 날짜의 박스오피스 데이터가 비어 있습니다.")
    st.info("💡 **확인 방법:** 영화진흥위원회 API의 당일 정산 및 집계가 늦어지는 경우가 있습니다. 잠시 후 다시 접속해 주세요.")

else:
    # 4. 데이터 가공 (문자열 숫자를 실제 숫자로 변환)
    box_office_list = data["boxOfficeResult"]["dailyBoxOfficeList"]
    df = pd.DataFrame(box_office_list)
    
    # 필요한 숫자 변수들을 정수형(int)으로 정밀하게 변환합니다.
    df['rank'] = df['rank'].astype(int)
    df['audiCnt'] = df['audiCnt'].astype(int)
    df['audiAcc'] = df['audiAcc'].astype(int)
    df['scrnCnt'] = df['scrnCnt'].astype(int)
    
    # 데이터프레임 순위 기준 오름차순 정렬
    df = df.sort_values(by='rank', ascending=True).reset_index(drop=True)
    
    # 5. 1위 영화 지표 카드 (Metric) 시각화
    top_movie = df.iloc[0]
    st.markdown(f"### 🏆 오늘의 1위 영화: **{top_movie['movieNm']}**")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # 전날 대비 순위 증감 표시 가공
        rank_inten = int(top_movie['rankInten'])
        delta_str = f"{rank_inten} 계단" if rank_inten == 0 else f"{rank_inten:+} 계단"
        st.metric(label="현재 순위", value="1 위", delta=delta_str if rank_inten != 0 else "변동 없음")
    with col2:
        st.metric(label="어제 관객 수", value=f"{top_movie['audiCnt']:,} 명")
    with col3:
        st.metric(label="누적 관객 수", value=f"{top_movie['audiAcc']:,} 명")
        
    st.divider()
    
    # 6. 관객 수 상위 5편 막대그래프 시각화
    st.subheader("📊 관객 수 Top 5 영화")
    df_top5 = df.head(5).copy()
    
    # Plotly 라이브러리로 깔끔하고 반응형인 막대그래프를 그립니다.
    fig = px.bar(
        df_top5, 
        x='movieNm', 
        y='audiCnt', 
        text='audiCnt',
        labels={'movieNm': '영화명', 'audiCnt': '당일 관객수(명)'},
        color='audiCnt',
        color_continuous_scale='Blues'
    )
    fig.update_traces(texttemplate='%{text}:,', textposition='outside')
    fig.update_layout(xaxis_title=None, coloraxis_showscale=False, height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # 7. 전체 박스오피스 표(Table) 시각화
    st.subheader("📋 전체 순위 및 상세 지표")
    
    # 화면에 보여줄 열만 선택하고 보기 좋은 이름으로 바꿉니다.
    df_display = df[['rank', 'movieNm', 'openDt', 'audiCnt', 'audiAcc', 'scrnCnt']].copy()
    df_display.columns = ['순위', '영화명', '개봉일', '당일 관객수', '누적 관객수', '스크린수']
    
    # 숫자에 콤마(,)를 붙여서 스트림릿 데이터프레임으로 출력합니다.
    st.dataframe(
        df_display.style.format({
            '당일 관객수': '{:,}',
            '누적 관객수': '{:,}',
            '스크린수': '{:,}'
        }),
        use_container_width=True,
        hide_index=True
    )
