from datetime import datetime, timedelta, timezone
from textwrap import fill

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="전일 흥행 연감 | 어제의 박스오피스", page_icon="🎞️", layout="wide")

# 별도 디자인 파일 없이, 이 파일 안에서 종이와 잉크를 닮은 색을 지정합니다.
# 제목은 기기에 설치된 궁서체를 쓰고, 없으면 명조체로 표시합니다.
# 긴 설명과 숫자는 읽기 편한 명조체로 두며, 외부 글꼴 다운로드는 필요 없습니다.
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #faf6ec, #efe5d1);
        color: #382d24;
    }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1120px; padding-top: 3rem; }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {
        font-family: "Noto Serif KR", "Batang", "바탕", serif;
        color: #382d24;
    }
    h1, h2, h3 {
        font-family: "Gungsuh", "GungsuhChe", "궁서", "궁서체", "Batang", "바탕", serif;
        font-weight: 400;
        color: #382d24;
        line-height: 1.6;
        word-break: keep-all;
        overflow-wrap: anywhere;
    }
    h1 {
        border-top: 3px double #8b7355;
        border-bottom: 1px solid #8b7355;
        padding: 1rem 0 !important;
        letter-spacing: 0.12em;
    }
    h3 { margin-top: 1.5rem; }
    [data-testid="stMarkdownContainer"] p { line-height: 1.9; }
    [data-testid="stCaptionContainer"] p { color: #75634f; }
    [data-testid="stMetric"] {
        background: #fffaf0;
        border: 1px solid #c4b18e;
        border-top: 3px solid #7b342d;
        border-radius: 3px;
        padding: 1.2rem;
        box-shadow: 0 3px 10px #382d2410;
    }
    [data-testid="stButton"] button {
        background: #7b342d;
        color: #fff8e9;
        border: 1px solid #652820;
        font-family: "Batang", "바탕", serif;
    }
    [data-testid="stButton"] button p { color: #fff8e9; }
    [data-testid="stButton"] button:hover {
        background: #652820;
        border-color: #382d24;
    }
    .edition-mark {
        color: #7b342d;
        font-family: "Gungsuh", "GungsuhChe", "궁서", "궁서체", "Batang", "바탕", serif;
        font-size: 0.85rem;
        letter-spacing: 0.25em;
    }
    </style>
    """,
    unsafe_allow_html=True,  # 위에 직접 작성한 고정된 스타일에만 사용합니다.
)

# 한국은 UTC보다 9시간 빠릅니다. 서버의 현지 시간 대신 한국 시간을 씁니다.
# datetime, timedelta, timezone은 파이썬 기본 기능이라 따로 설치하지 않습니다.
KST = timezone(timedelta(hours=9))
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/"
    "searchDailyBoxOfficeList.json"
)


# 같은 날짜를 반복 조회하면 10분 동안 결과를 재사용합니다.
# 요청 실패나 API 오류는 예외로 처리하므로 캐시에 저장되지 않습니다.
@st.cache_data(ttl=600, show_spinner=False)
def load_box_office(target_date, api_key):
    response = requests.get(
        API_URL,
        params={"key": api_key, "targetDt": target_date},
        timeout=15,  # 서버 응답을 무한정 기다리지 않습니다.
    )
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError:
        raise ValueError(
            "도착한 회신이 정해진 JSON 형식을 갖추지 못하여, 흥행 기록의 해독을 마치지 못하였사옵니다. "
            "KOBIS 서비스의 운영 상태를 확인하신 뒤, 잠시 후 다시 열람하여 주시옵소서."
        ) from None

    if not isinstance(data, dict):
        raise ValueError(
            "회신의 형식이 규정된 체계와 부합하지 않아 기록을 펼칠 수 없사옵니다. "
            "KOBIS 서비스의 운영 상태를 확인하여 주시옵소서."
        )

    # 인증키가 잘못되어도 HTTP 200일 수 있어 오류 상자도 직접 확인합니다.
    result = data.get("boxOfficeResult")
    if "faultInfo" in data or (
        isinstance(result, dict) and "faultInfo" in result
    ):
        raise ValueError(
            "KOBIS로부터 오류 통지(faultInfo)가 당도하여, 금번의 열람을 진행하지 못하였사옵니다. "
            "Secrets에 보관한 KOBIS_KEY가 발급받으신 인증키와 정확히 일치하는지 살피시고, "
            "인증키의 사용 가능 여부와 API 호출 한도 또한 확인하여 주시옵소서."
        )

    if not isinstance(result, dict):
        raise ValueError(
            "회신 가운데 흥행 기록을 담는 boxOfficeResult 항목이 누락되어 있사옵니다. "
            "KOBIS 서비스의 운영 상태와 API 응답 형식을 확인하여 주시옵소서."
        )

    movies = result.get("dailyBoxOfficeList")
    if not isinstance(movies, list):
        raise ValueError(
            "회신에 수록된 영화 목록이 정해진 형식을 갖추지 못하였사옵니다. "
            "KOBIS 서비스의 운영 상태와 API 응답 형식을 확인하여 주시옵소서."
        )
    if not movies:
        raise ValueError(
            "전일의 영화 목록이 아직 비어 있어, 이 지면에 옮겨 적을 기록이 없사옵니다. "
            "이는 관객 집계 또는 자료 반영의 지연에서 비롯될 수 있사오니, "
            "KOBIS에 해당 날짜의 자료가 등록되었는지 확인하신 뒤 잠시 후 다시 열람하여 주시옵소서."
        )
    return movies


def show_audience_chart(df):
    # 제목을 막대 위에 놓으면 작은 화면에서도 그래프 너비를 넉넉히 쓸 수 있습니다.
    top5 = df.nlargest(5, "관객수").copy()
    top5["제목표시"] = top5.apply(
        lambda movie: fill(f"{movie['순위']}위 · {movie['영화명']}", width=18), axis=1
    )
    top5["관객표시"] = top5["관객수"].map(lambda count: f"{count:,}명")
    title_lines = max(title.count("\n") + 1 for title in top5["제목표시"])
    row_height = max(80, title_lines * 18 + 48)
    bar_offset = row_height / 2 - 22

    # Vega-Lite는 Streamlit의 기본 차트 기능입니다. 추가 라이브러리는 필요 없습니다.
    # 제목, 막대, 숫자를 겹쳐 그리되 숫자 오른쪽에 충분한 여백을 남깁니다.
    spec = {
        "height": row_height * len(top5),
        "autosize": {"type": "fit-x", "contains": "padding", "resize": True},
        "background": "#faf6ec",
        "padding": {"left": 8, "right": 16, "top": 8, "bottom": 8},
        "encoding": {
            "y": {
                "field": "영화명", "type": "nominal",
                "sort": top5["영화명"].tolist(), "axis": None,
                "scale": {"paddingInner": 0, "paddingOuter": 0},
            },
            "x": {
                "field": "관객수", "type": "quantitative",
                "scale": {"domain": [0, max(int(top5["관객수"].max()) * 1.5, 1)]},
                "axis": {
                    "title": "어제 관객수 (명)", "format": ",.0f", "tickCount": 3,
                    "tickMinStep": 1, "domain": False, "ticks": False,
                    "gridColor": "#dfd3be", "gridDash": [3, 5],
                    "labelPadding": 8, "titlePadding": 14,
                },
            },
            "tooltip": [
                {"field": "영화명", "type": "nominal", "title": "영화명"},
                {"field": "순위", "type": "ordinal", "title": "박스오피스 순위"},
                {"field": "관객수", "type": "quantitative", "title": "어제 관객수 (명)", "format": ",.0f"},
                {"field": "누적관객", "type": "quantitative", "title": "누적관객 (명)", "format": ",.0f"},
                {"field": "개봉일", "type": "nominal", "title": "개봉일"},
            ],
        },
        "layer": [
            {
                # 선택 설정은 막대에만 붙입니다. 전체에 붙이면 여러 계층에서
                # 같은 이름의 신호가 중복 생성되어 그래프가 안 보일 수 있습니다.
                "params": [{
                    "name": "hover_movie",
                    "select": {
                        "type": "point", "fields": ["영화명"],
                        "on": "pointerover", "clear": "pointerout", "toggle": False,
                    },
                }],
                "mark": {"type": "bar", "size": 20, "cornerRadiusEnd": 4, "yOffset": bar_offset},
                "encoding": {
                    "color": {
                        "condition": {"test": "datum['순위'] === 1", "value": "#7b342d"},
                        "value": "#a88966",
                    },
                    "opacity": {
                        "condition": {"param": "hover_movie", "value": 1}, "value": 0.5,
                    },
                },
            },
            {
                "mark": {
                    "type": "text", "align": "left", "baseline": "top",
                    "dy": -row_height / 2 + 8, "fontSize": 14,
                    # 그래프에서도 작품명만 궁서체로 강조합니다.
                    "font": "Gungsuh, GungsuhChe, 궁서, 궁서체, Batang, serif",
                    "fontWeight": "normal", "lineBreak": "\n", "lineHeight": 18,
                },
                "encoding": {"x": {"value": 0}, "text": {"field": "제목표시"}},
            },
            {
                "mark": {
                    "type": "text", "align": "left", "baseline": "middle",
                    "dx": 8, "dy": bar_offset, "fontSize": 13, "fontWeight": "bold",
                },
                "encoding": {"text": {"field": "관객표시"}},
            },
        ],
        "config": {
            "view": {"stroke": None},
            "font": "Batang, Noto Serif KR, serif",
            "text": {"color": "#382d24"},
            "axis": {"labelColor": "#75634f", "titleColor": "#75634f"},
        },
    }
    description = "어제 관객수 상위 작품을 관객수 내림차순으로 비교한 가로 막대그래프. "
    description += "; ".join(
        f"{movie['영화명']}: {movie['관객수']:,}명"
        for _, movie in top5.iterrows()
    )
    # 접근성 설명은 차트 명세에 넣어 구버전에서도 지원하도록 합니다.
    spec["description"] = description
    st.vega_lite_chart(top5, spec, use_container_width=True, theme=None)


def main():
    # 날짜 계산은 캐시 바깥에서 실행하여 한국의 날짜가 바뀌면 새 날짜를 씁니다.
    yesterday = datetime.now(KST).date() - timedelta(days=1)
    target_date = yesterday.strftime("%Y%m%d")  # API는 여덟 자리 날짜를 받습니다.

    st.markdown('<div class="edition-mark">映 畫 · 日 日 記 錄</div>', unsafe_allow_html=True)
    st.title("전일 흥행 연감")
    st.markdown(
        "어제의 박스오피스에 아로새겨진 관객의 발자취를 삼가 모아, "
        "은막을 수놓은 작품들의 흥행 성세와 그 누적의 궤적을 이 한 장의 지면에 펼쳐 보이옵니다."
    )
    st.caption(
        f"기록의 기준일 · {yesterday:%Y년 %m월 %d일} (한국 시간의 어제) "
        "│ 자료의 출전 · 영화진흥위원회 KOBIS"
    )

    # 인증키는 코드에 적거나 화면에 출력하지 않고 Streamlit Secrets에서 읽습니다.
    try:
        api_key = st.secrets["KOBIS_KEY"]
    except (FileNotFoundError, KeyError):
        st.error(
            '열람에 필요한 인증키가 비밀 금고에서 발견되지 않았사옵니다. '
            'Streamlit Cloud의 앱 설정 → Secrets를 여시어, '
            'KOBIS_KEY = "발급받은 인증키" 형식으로 저장하여 주시옵소서.'
        )
        return

    if not isinstance(api_key, str) or not api_key.strip():
        st.error(
            '비밀 금고에 보관된 인증키가 비어 있거나 문자열 형식을 갖추지 못하였사옵니다. '
            'Secrets의 KOBIS_KEY에 실제 인증키를 큰따옴표로 감싸 입력하여 주시옵소서.'
        )
        return

    # 버튼을 누르면 앱이 다시 실행됩니다. 실패한 요청은 캐시되지 않아 재시도됩니다.
    st.button("전일의 기록을 다시 열람하다")
    st.caption("한 차례 무사히 수신한 기록은 10분간 보관하여, 거듭된 열람에 활용하옵니다.")

    try:
        with st.spinner("전일의 흥행 기록을 청하여 이 지면에 옮기는 중이옵니다…"):
            movies = load_box_office(target_date, api_key.strip())
    except requests.exceptions.Timeout:
        st.error(
            "정해진 기다림의 시간이 다하였으나 회신이 도착하지 않았사옵니다. "
            "네트워크 연결과 KOBIS 서비스의 운영 상태를 살피신 뒤 다시 열람하여 주시옵소서."
        )
        return
    except requests.exceptions.RequestException:
        # 예외 원문에는 인증키가 들어간 URL이 포함될 수 있어 출력하지 않습니다.
        st.error(
            "KOBIS에 청한 자료를 수신하지 못하여, 기록의 편찬이 잠시 멈추었사옵니다. "
            "네트워크 연결, KOBIS 서비스의 운영 상태, API 호출 한도를 확인하여 주시옵소서."
        )
        return
    except ValueError as error:
        st.error(str(error))
        return

    # API의 영어 필드명을 표에 사용할 한국어 열 이름으로 바꿉니다.
    columns = {
        "rank": "순위",
        "movieNm": "영화명",
        "openDt": "개봉일",
        "audiCnt": "관객수",
        "audiAcc": "누적관객",
        "scrnCnt": "스크린수",
    }
    try:
        df = pd.DataFrame(movies)[list(columns)].rename(columns=columns)
        # 숫자도 문자열로 오므로 정렬과 그래프를 만들기 전에 숫자로 바꿉니다.
        for column in ["순위", "관객수", "누적관객", "스크린수"]:
            df[column] = pd.to_numeric(df[column], errors="raise").astype("int64")
        df = df.sort_values("순위").reset_index(drop=True)
        first_place = df.loc[df["순위"] == 1].iloc[0]
    except (KeyError, ValueError, TypeError, OverflowError, IndexError):
        st.error(
            "도착한 영화 자료에 필수 항목이 빠졌거나 수치의 표기가 온전하지 않아, "
            "흥행 순위와 통계를 정리하지 못하였사옵니다. "
            "KOBIS 응답 형식을 확인하신 뒤 잠시 후 다시 열람하여 주시옵소서."
        )
        return

    st.subheader(f"흥행의 수위에 오른 작품 · 1위, {first_place['영화명']}")
    st.markdown(
        "전일 가장 많은 관객의 선택을 받은 작품이옵니다. 하루의 관객수와 누적관객, "
        "그리고 스크린수를 나란히 두어, 그 성세의 일면을 헤아려 보시옵소서."
    )
    card1, card2, card3 = st.columns(3)
    card1.metric("어제 관객수", f"{first_place['관객수']:,}명")
    card2.metric("누적관객", f"{first_place['누적관객']:,}명")
    card3.metric("스크린수", f"{first_place['스크린수']:,}개")

    st.subheader("관객 동원의 성세 · 상위 다섯 작품")
    st.caption(
        "관객수가 많은 작품부터 위에 모시고, 각 막대의 끝에 관객수를 밝혀 적었사옵니다. "
        "작품명 앞의 숫자는 박스오피스 순위이며, 짙은 적갈색은 1위 작품을 가리키옵니다."
    )
    show_audience_chart(df)
    st.caption("막대나 작품명에 마우스를 올리시면 개봉일과 누적관객을 함께 살펴보실 수 있사옵니다.")

    st.subheader("전일 박스오피스 순위 · 작품별 흥행 일람")
    st.caption("순위와 영화명, 개봉일 및 관객·스크린의 수효를 아래의 일람에 갖추어 기록하옵니다.")
    st.dataframe(df, hide_index=True, width="stretch")
    st.caption("— 전일의 은막을 비춘 관객의 발자취를 여기에 갈무리하옵니다. —")


if __name__ == "__main__":
    main()
