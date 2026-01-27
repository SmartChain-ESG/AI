"""
TBM Safety API Test UI
Streamlit 기반 테스트 인터페이스

실행 방법:
    cd apps/safety_api
    streamlit run tests/test_tbm_ui.py
    streamlit run tests/test_tbm_ui.py --server.port 8501
"""

import streamlit as st
import requests
from typing import Optional

# 페이지 설정
st.set_page_config(
    page_title="TBM Safety API Tester",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API 기본 URL
DEFAULT_API_URL = "http://127.0.0.1:8000"


# =====================================================
# API 호출 함수
# =====================================================

def get_api_url() -> str:
    """사이드바에서 설정된 API URL 반환"""
    return st.session_state.get("api_url", DEFAULT_API_URL)


def check_api_health() -> dict:
    """API 서버 상태 확인"""
    try:
        response = requests.get(f"{get_api_url()}/health", timeout=5)
        if response.status_code == 200:
            return {"status": "healthy", "data": response.json()}
        return {"status": "error", "message": f"Status {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "서버에 연결할 수 없습니다"}
    except requests.exceptions.Timeout:
        return {"status": "error", "message": "연결 시간 초과"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_api_info() -> dict:
    """API 기본 정보 조회"""
    try:
        response = requests.get(f"{get_api_url()}/", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def call_person_count_api(video_file, sample_interval: int, expected_count: Optional[int]) -> dict:
    """인원 수 분석 API 호출"""
    files = {"file": (video_file.name, video_file.getvalue(), "video/mp4")}
    data = {"sample_interval": sample_interval}

    if expected_count is not None:
        data["expected_person_count"] = expected_count

    response = requests.post(
        f"{get_api_url()}/analyze/person-count",
        files=files,
        data=data,
        timeout=120
    )
    response.raise_for_status()
    return response.json()


def call_helmet_compliance_api(video_file, sample_interval: int, required_compliance: float) -> dict:
    """헬멧 착용 검사 API 호출"""
    files = {"file": (video_file.name, video_file.getvalue(), "video/mp4")}
    data = {
        "sample_interval": sample_interval,
        "required_compliance": required_compliance
    }

    response = requests.post(
        f"{get_api_url()}/analyze/helmet-compliance",
        files=files,
        data=data,
        timeout=120
    )
    response.raise_for_status()
    return response.json()


def call_speech_compliance_api(video_file, min_coverage: float) -> dict:
    """음성 분석 API 호출"""
    files = {"file": (video_file.name, video_file.getvalue(), "video/mp4")}
    data = {"min_coverage": min_coverage}

    response = requests.post(
        f"{get_api_url()}/analyze/speech-compliance",
        files=files,
        data=data,
        timeout=300
    )
    response.raise_for_status()
    return response.json()


def call_full_analysis_api(video_file, config: dict) -> dict:
    """전체 분석 API 호출"""
    files = {"file": (video_file.name, video_file.getvalue(), "video/mp4")}

    response = requests.post(
        f"{get_api_url()}/analyze/full",
        files=files,
        data=config,
        timeout=300
    )
    response.raise_for_status()
    return response.json()


# =====================================================
# 결과 표시 함수
# =====================================================

def display_person_result(result: dict):
    """인원 수 분석 결과 표시"""
    st.subheader("👥 인원 수 분석 결과")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg = result.get('average_count', 0)
        st.metric("평균 인원", f"{avg:.1f}명")
    with col2:
        st.metric("최대 인원", f"{result.get('max_count', 0)}명")
    with col3:
        st.metric("최소 인원", f"{result.get('min_count', 0)}명")
    with col4:
        st.metric("샘플 프레임", f"{result.get('sampled_frames', 0)}개")

    # Pass/Fail 표시
    if result.get("expected_person_count") is not None:
        expected = result["expected_person_count"]
        person_pass = result.get("person_pass", False)

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**기대 인원:** {expected}명")
        with col2:
            if person_pass:
                st.success(f"**PASS** (최대 {result['max_count']}명 >= {expected}명)")
            else:
                st.error(f"**FAIL** (최대 {result['max_count']}명 < {expected}명)")

    # 프레임별 인원 수
    with st.expander("프레임별 인원 수 상세"):
        detections = result.get("detections_per_frame", [])
        if detections:
            st.line_chart(detections)
            st.caption(f"총 {len(detections)}개 프레임 분석")
        else:
            st.info("데이터 없음")


def display_helmet_result(result: dict):
    """헬멧 착용 결과 표시"""
    st.subheader("🪖 헬멧 착용 검사 결과")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        compliance = result.get("average_compliance", 0)
        st.metric("평균 착용률", f"{compliance:.1f}%")
    with col2:
        st.metric("최소 착용률", f"{result.get('min_compliance', 0):.1f}%")
    with col3:
        st.metric("최대 착용률", f"{result.get('max_compliance', 0):.1f}%")
    with col4:
        st.metric("샘플 프레임", f"{result.get('sampled_frames', 0)}개")

    # Pass/Fail
    st.divider()
    overall_pass = result.get("overall_pass", False)
    if overall_pass:
        st.success("**PASS** - 헬멧 착용 기준 충족")
    else:
        st.error("**FAIL** - 헬멧 착용 기준 미달")

    # 위반 사항
    violations = result.get("violations", [])
    if violations:
        st.warning(f"{len(violations)}개 프레임에서 기준 미달 감지")
        with st.expander(f"위반 프레임 상세 ({len(violations)}개)"):
            for v in violations[:10]:
                st.write(f"- 프레임 {v['frame_number']}: 착용률 {v['compliance_rate']:.1f}% "
                        f"(착용 {v['helmet_count']}명, 미착용 {v['no_helmet_count']}명)")
            if len(violations) > 10:
                st.caption(f"... 외 {len(violations) - 10}개")

    # 감지 방법
    method = result.get("detection_method", "unknown")
    if method == "color_based":
        st.info("색상 기반 임시 감지 방식 사용 중")
    elif method == "custom_model":
        st.success("커스텀 학습 모델 사용 중")


def display_speech_result(result: dict):
    """음성 분석 결과 표시"""
    st.subheader("🎤 음성 분석 결과")

    keyword_analysis = result.get("keyword_analysis", {})

    col1, col2, col3 = st.columns(3)

    with col1:
        coverage = keyword_analysis.get("keyword_coverage", 0)
        st.metric("키워드 포함률", f"{coverage:.1f}%")
    with col2:
        found_count = keyword_analysis.get("found_count", 0)
        total_count = keyword_analysis.get("total_keywords", 0)
        st.metric("발견 키워드", f"{found_count}/{total_count}")
    with col3:
        compliant = result.get("compliant", False)
        if compliant:
            st.success("**PASS**")
        else:
            st.error("**FAIL**")

    # 키워드 상세
    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        found_keywords = keyword_analysis.get("found_keywords", [])
        st.markdown(f"**발견된 키워드 ({len(found_keywords)}개)**")
        if found_keywords:
            for kw in found_keywords:
                st.markdown(f"- :green[{kw}]")
        else:
            st.write("없음")

    with col2:
        missing_keywords = keyword_analysis.get("missing_keywords", [])
        st.markdown(f"**누락된 키워드 ({len(missing_keywords)}개)**")
        if missing_keywords:
            for kw in missing_keywords:
                st.markdown(f"- :red[{kw}]")
        else:
            st.write("없음")

    # 전사 텍스트
    with st.expander("음성 전사 텍스트"):
        transcription = result.get("transcription", "")
        if transcription:
            st.text_area("전사 결과", transcription, height=150, disabled=True)
        else:
            st.write("전사 결과 없음")


def display_full_analysis_result(result: dict):
    """전체 분석 결과 표시"""
    st.header("TBM 종합 분석 결과")

    # 최종 판정
    overall_pass = result.get("overall_compliance", False)
    compliance_summary = result.get("compliance_summary", {})

    if overall_pass:
        st.success("# TBM 승인")
        st.balloons()
    else:
        st.error("# TBM 재촬영 필요")

    st.divider()

    # 요약 메트릭
    st.subheader("종합 점수")
    col1, col2, col3 = st.columns(3)

    with col1:
        person_pass = compliance_summary.get("person_pass")
        if person_pass is not None:
            if person_pass:
                st.success("**인원 검증 PASS**")
            else:
                st.error("**인원 검증 FAIL**")
        else:
            st.info("**인원 검증 미실시**")

    with col2:
        helmet_pass = compliance_summary.get("helmet_pass", False)
        helmet_compliance = compliance_summary.get("helmet_compliance", 0)
        if helmet_compliance is not None:
            if helmet_pass:
                st.success(f"**헬멧 PASS**\n\n{helmet_compliance:.1f}%")
            else:
                st.error(f"**헬멧 FAIL**\n\n{helmet_compliance:.1f}%")
        else:
            st.info("**헬멧 검사 불가**")

    with col3:
        speech_pass = compliance_summary.get("speech_pass", False)
        speech_compliance = compliance_summary.get("speech_compliance", 0)
        if speech_pass:
            st.success(f"**음성 PASS**\n\n{speech_compliance:.1f}%")
        else:
            st.error(f"**음성 FAIL**\n\n{speech_compliance:.1f}%")

    # 상세 결과 탭
    st.divider()
    st.subheader("상세 분석 결과")

    tab1, tab2, tab3 = st.tabs(["👥 인원 수", "🪖 헬멧 착용", "🎤 음성 분석"])

    with tab1:
        person_result = result.get("person_detection", {})
        if person_result:
            display_person_result(person_result)

    with tab2:
        helmet_result = result.get("helmet_detection", {})
        if helmet_result:
            display_helmet_result(helmet_result)

    with tab3:
        speech_result = result.get("speech_analysis", {})
        if speech_result:
            display_speech_result(speech_result)


# =====================================================
# 메인 UI
# =====================================================

def main():
    st.title("🏗️ TBM Safety API Tester")
    st.caption("건설 현장 안전 점검 회의(TBM) 영상 분석 테스트")

    # ===== 사이드바 =====
    with st.sidebar:
        st.header("설정")

        # API URL 설정
        api_url = st.text_input("API URL", value=DEFAULT_API_URL)
        st.session_state["api_url"] = api_url

        # API 상태 확인
        if st.button("API 상태 확인", use_container_width=True):
            with st.spinner("확인 중..."):
                health = check_api_health()
                if health["status"] == "healthy":
                    st.success("API 서버 정상")
                    info = get_api_info()
                    if info:
                        st.json(info.get("models", {}))
                else:
                    st.error(f"연결 실패: {health['message']}")

        st.divider()

        # 분석 옵션
        st.subheader("분석 옵션")

        sample_interval = st.slider(
            "프레임 샘플링 간격",
            min_value=10,
            max_value=90,
            value=30,
            step=10,
            help="N번째 프레임마다 분석"
        )

        st.divider()

        # 인원 수 기준
        st.subheader("인원 수 검증")
        enable_person_check = st.checkbox("인원 수 검증 활성화", value=False)
        expected_person_count = None
        if enable_person_check:
            expected_person_count = st.number_input(
                "기대 인원 수",
                min_value=1,
                max_value=50,
                value=5
            )

        st.divider()

        # 헬멧 착용 기준
        st.subheader("헬멧 착용 기준")
        required_helmet_compliance = st.slider(
            "필수 착용률 (%)",
            min_value=0.0,
            max_value=100.0,
            value=100.0,
            step=5.0
        )

        st.divider()

        # 음성 분석 기준
        st.subheader("음성 분석 기준")
        required_keyword_coverage = st.slider(
            "필수 키워드 포함률 (%)",
            min_value=0.0,
            max_value=100.0,
            value=80.0,
            step=5.0
        )

    # ===== 메인 영역 =====
    st.header("비디오 업로드")

    uploaded_file = st.file_uploader(
        "TBM 비디오 파일 선택",
        type=["mp4", "avi", "mov"],
        help="촬영한 TBM 영상을 업로드하세요"
    )

    if uploaded_file is not None:
        file_size_mb = uploaded_file.size / 1024 / 1024
        st.success(f"파일: {uploaded_file.name} ({file_size_mb:.2f} MB)")

        st.divider()
        st.header("분석 실행")

        analysis_mode = st.radio(
            "분석 방법 선택",
            ["전체 분석 (권장)", "인원 수만", "헬멧만", "음성만"],
            horizontal=True
        )

        st.divider()

        if st.button("분석 시작", type="primary", use_container_width=True):

            try:
                if analysis_mode == "전체 분석 (권장)":
                    with st.spinner("전체 분석 진행 중..."):
                        config = {
                            "sample_interval": sample_interval,
                            "required_helmet_compliance": required_helmet_compliance,
                            "required_keyword_coverage": required_keyword_coverage,
                        }
                        if enable_person_check and expected_person_count:
                            config["expected_person_count"] = expected_person_count

                        result = call_full_analysis_api(uploaded_file, config)
                    display_full_analysis_result(result)

                elif analysis_mode == "인원 수만":
                    with st.spinner("인원 수 분석 중..."):
                        result = call_person_count_api(
                            uploaded_file,
                            sample_interval,
                            expected_person_count if enable_person_check else None
                        )
                    display_person_result(result)

                elif analysis_mode == "헬멧만":
                    with st.spinner("헬멧 착용 검사 중..."):
                        result = call_helmet_compliance_api(
                            uploaded_file,
                            sample_interval,
                            required_helmet_compliance
                        )
                    display_helmet_result(result)

                elif analysis_mode == "음성만":
                    with st.spinner("음성 분석 중..."):
                        result = call_speech_compliance_api(
                            uploaded_file,
                            required_keyword_coverage
                        )
                    display_speech_result(result)

                # 원본 JSON
                st.divider()
                with st.expander("원본 JSON 응답"):
                    st.json(result)

            except requests.exceptions.ConnectionError:
                st.error("API 서버에 연결할 수 없습니다.")
                st.code("cd apps/safety_api && uvicorn app.main:app --reload", language="bash")

            except requests.exceptions.Timeout:
                st.error("요청 시간 초과")

            except requests.exceptions.HTTPError as e:
                st.error(f"HTTP 오류: {e.response.status_code}")
                st.code(e.response.text)

            except Exception as e:
                st.error(f"오류 발생: {str(e)}")
                st.exception(e)

    else:
        st.info("비디오 파일을 업로드하여 분석을 시작하세요")

        # 사용법 안내
        with st.expander("사용법"):
            st.markdown("""
            ### 1. API 서버 실행
            ```bash
            cd apps/safety_api
            uvicorn app.main:app --reload
            ```

            ### 2. 비디오 업로드
            - MP4, AVI, MOV 형식 지원
            - TBM 회의 영상 업로드

            ### 3. 분석 옵션 설정
            - 사이드바에서 기준값 설정
            - 인원 수, 헬멧 착용률, 키워드 포함률

            ### 4. 분석 실행
            - 전체 분석 또는 개별 항목 분석 선택
            """)


if __name__ == "__main__":
    main()
