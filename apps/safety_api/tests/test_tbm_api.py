"""
TBM Safety API 종합 테스트 스크립트
API 문서 기준으로 모든 엔드포인트 테스트
"""
import requests
import json
from pathlib import Path
import time

# 설정
BASE_URL = "http://127.0.0.1:8000"
TEST_VIDEO = "test_video.mp4"  # 테스트할 비디오 파일

class Colors:
    """터미널 색상"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text):
    """헤더 출력"""
    print(f"\n{'='*70}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print('='*70)

def print_success(text):
    """성공 메시지"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    """에러 메시지"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    """경고 메시지"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def test_root():
    """1. Root 엔드포인트 테스트"""
    print_header("TEST 1: Root Endpoint (GET /)")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n응답:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 모델 상태 확인
            models = data.get('models', {})
            print(f"\n모델 상태:")
            print(f"  - Person Detector: {models.get('person_detector', False)}")
            print(f"  - Helmet Detector: {models.get('helmet_detector', False)}")
            print(f"  - Speech Analyzer: {models.get('speech_analyzer', False)}")
            
            print_success("Root 엔드포인트 테스트 통과")
            return True
        else:
            print_error(f"예상치 못한 상태 코드: {response.status_code}")
            return False
            
    except Exception as e:
        print_error(f"테스트 실패: {e}")
        return False

def test_health():
    """2. Health Check 테스트"""
    print_header("TEST 2: Health Check (GET /health)")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n응답:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print_success("Health Check 테스트 통과")
            return True
        else:
            print_warning(f"Health 엔드포인트가 없거나 오류: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_warning(f"Health 엔드포인트 미구현 또는 오류: {e}")
        return False

def test_person_count(video_path):
    """3. 인원 수 분석 테스트"""
    print_header("TEST 3: Person Count Analysis (POST /analyze/person-count)")
    
    if not Path(video_path).exists():
        print_error(f"비디오 파일을 찾을 수 없습니다: {video_path}")
        print_warning("이 테스트를 건너뜁니다.")
        return False
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path, f, 'video/mp4')}
            data = {'sample_interval': 30}
            
            print(f"📤 업로드 중: {video_path}")
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/analyze/person-count",
                files=files,
                data=data,
                timeout=120
            )
            
            elapsed = time.time() - start_time
            print(f"⏱️  처리 시간: {elapsed:.2f}초")
            print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 분석 결과:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 주요 정보 출력
            print(f"\n✨ 요약:")
            print(f"  - 평균 인원: {data.get('average_count', 'N/A')}")
            print(f"  - 최대 인원: {data.get('max_count', 'N/A')}")
            print(f"  - 최소 인원: {data.get('min_count', 'N/A')}")
            
            print_success("인원 수 분석 테스트 통과")
            return True
        else:
            print_error(f"분석 실패: {response.status_code}")
            print(f"응답: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"요청 실패: {e}")
        return False
    except Exception as e:
        print_error(f"테스트 실패: {e}")
        return False

def test_helmet_compliance(video_path):
    """4. 헬멧 착용 분석 테스트"""
    print_header("TEST 4: Helmet Compliance (POST /analyze/helmet-compliance)")
    
    if not Path(video_path).exists():
        print_error(f"비디오 파일을 찾을 수 없습니다: {video_path}")
        print_warning("이 테스트를 건너뜁니다.")
        return False
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path, f, 'video/mp4')}
            data = {
                'sample_interval': 30,
                'required_compliance': 100.0
            }
            
            print(f"📤 업로드 중: {video_path}")
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/analyze/helmet-compliance",
                files=files,
                data=data,
                timeout=120
            )
            
            elapsed = time.time() - start_time
            print(f"⏱️  처리 시간: {elapsed:.2f}초")
            print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 분석 결과:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 주요 정보 출력
            print(f"\n✨ 요약:")
            print(f"  - 평균 준수율: {data.get('average_compliance', 'N/A')}%")
            print(f"  - 최소 준수율: {data.get('min_compliance', 'N/A')}%")
            print(f"  - 전체 통과: {data.get('overall_pass', 'N/A')}")
            print(f"  - 위반 건수: {len(data.get('violations', []))}")
            
            print_success("헬멧 착용 분석 테스트 통과")
            return True
        else:
            print_error(f"분석 실패: {response.status_code}")
            print(f"응답: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"요청 실패: {e}")
        return False
    except Exception as e:
        print_error(f"테스트 실패: {e}")
        return False

def test_speech_compliance(video_path):
    """5. 음성 분석 테스트"""
    print_header("TEST 5: Speech Compliance (POST /analyze/speech-compliance)")
    
    if not Path(video_path).exists():
        print_error(f"비디오 파일을 찾을 수 없습니다: {video_path}")
        print_warning("이 테스트를 건너뜁니다.")
        return False
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path, f, 'video/mp4')}
            data = {'min_coverage': 80.0}
            
            print(f"📤 업로드 중: {video_path}")
            print("⏳ 음성 분석은 시간이 걸릴 수 있습니다...")
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/analyze/speech-compliance",
                files=files,
                data=data,
                timeout=300  # 5분
            )
            
            elapsed = time.time() - start_time
            print(f"⏱️  처리 시간: {elapsed:.2f}초")
            print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 분석 결과:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 주요 정보 출력
            keyword_analysis = data.get('keyword_analysis', {})
            print(f"\n✨ 요약:")
            print(f"  - 발견된 키워드: {keyword_analysis.get('found_keywords', [])}")
            print(f"  - 누락된 키워드: {keyword_analysis.get('missing_keywords', [])}")
            print(f"  - 키워드 포함률: {keyword_analysis.get('keyword_coverage', 'N/A')}%")
            print(f"  - 준수 여부: {data.get('compliant', 'N/A')}")
            
            print_success("음성 분석 테스트 통과")
            return True
        else:
            print_error(f"분석 실패: {response.status_code}")
            print(f"응답: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"요청 실패: {e}")
        return False
    except Exception as e:
        print_error(f"테스트 실패: {e}")
        return False

def test_full_analysis(video_path):
    """6. 전체 분석 테스트"""
    print_header("TEST 6: Full Analysis (POST /analyze/full)")
    
    if not Path(video_path).exists():
        print_error(f"비디오 파일을 찾을 수 없습니다: {video_path}")
        print_warning("이 테스트를 건너뜁니다.")
        return False
    
    try:
        with open(video_path, 'rb') as f:
            files = {'file': (video_path, f, 'video/mp4')}
            data = {
                'sample_interval': 30,
                'required_helmet_compliance': 100.0,
                'required_keyword_coverage': 80.0
            }
                        
            print(f"📤 업로드 중: {video_path}")
            print("⏳ 전체 분석은 시간이 걸릴 수 있습니다...")
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/analyze/full",
                files=files,
                data=data,  
                timeout=300
            )
            
            elapsed = time.time() - start_time
            print(f"⏱️  처리 시간: {elapsed:.2f}초")
            print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📊 분석 결과:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 종합 요약
            compliance_summary = data.get('compliance_summary', {})
            print(f"\n✨ 종합 요약:")
            print(f"  - 헬멧 준수율: {compliance_summary.get('helmet_compliance', 'N/A')}%")
            print(f"  - 음성 준수율: {compliance_summary.get('speech_compliance', 'N/A')}%")
            print(f"  - 헬멧 통과: {compliance_summary.get('helmet_pass', 'N/A')}")
            print(f"  - 음성 통과: {compliance_summary.get('speech_pass', 'N/A')}")
            print(f"  - 전체 통과: {compliance_summary.get('overall_pass', 'N/A')}")
            
            print_success("전체 분석 테스트 통과")
            return True
        else:
            print_error(f"분석 실패: {response.status_code}")
            print(f"응답: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_error(f"요청 실패: {e}")
        return False
    except Exception as e:
        print_error(f"테스트 실패: {e}")
        return False

def main():
    """전체 테스트 실행"""
    print("\n" + "="*70)
    print(f"{Colors.BLUE}🎬 TBM Safety API 종합 테스트 시작{Colors.END}")
    print("="*70)
    
    results = []
    
    # 1. Root 테스트
    results.append(("Root", test_root()))
    
    # 2. Health Check 테스트
    results.append(("Health Check", test_health()))
    
    # 비디오 파일 확인
    if not Path(TEST_VIDEO).exists():
        print_warning(f"\n테스트 비디오 파일이 없습니다: {TEST_VIDEO}")
        print("💡 다음 방법 중 하나를 선택하세요:")
        print("   1. test_video.mp4 파일을 프로젝트 루트에 준비")
        print("   2. 스크립트 상단의 TEST_VIDEO 변수를 실제 파일 경로로 수정")
        print("\n기본 테스트만 계속 진행합니다...")
    else:
        # 3. 인원 수 분석
        results.append(("Person Count", test_person_count(TEST_VIDEO)))
        
        # 4. 헬멧 착용 분석
        results.append(("Helmet Compliance", test_helmet_compliance(TEST_VIDEO)))
        
        # 5. 음성 분석
        results.append(("Speech Compliance", test_speech_compliance(TEST_VIDEO)))
        
        # 6. 전체 분석
        results.append(("Full Analysis", test_full_analysis(TEST_VIDEO)))
    
    # 결과 요약
    print_header("테스트 결과 요약")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{name:.<30} {status}")
    
    print(f"\n전체: {passed}/{total} 통과")
    
    if passed == total:
        print_success("\n🎉 모든 테스트 통과!")
    elif passed > 0:
        print_warning(f"\n⚠️  일부 테스트 실패 ({total - passed}개)")
    else:
        print_error("\n❌ 모든 테스트 실패")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    main()