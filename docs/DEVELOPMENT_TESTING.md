# 개발·테스트·구현체 등록 절차

## 1단계: 자기 코드만 작성

`core/interfaces.py`에서 본인이 구현할 ABC 메서드와 `core/models.py`의 Output을 확인합니다. 자기 디렉터리 내부 구조는 자유롭게 변경할 수 있습니다.

## 2단계: Fixture로 독립 테스트

```python
from tests.fixtures.contract_samples import sample_transcripts
from ai.stub import StubPreprocessor

transcript = sample_transcripts()[0]
result = StubPreprocessor().preprocess(transcript)
assert result.source_transcript_id == transcript.id
```

- AI 담당은 Whisper 없이 `sample_transcripts()`를 사용합니다.
- 영상처리 담당은 `examples/demo.mp4`와 고정 승인 계획을 사용합니다.
- Application 담당은 모든 기능을 Stub으로 주입해 함수 단위로 검증합니다.

## 3단계: 구현이 준비되면 등록

[`bootstrap.py`](../src/bootstrap.py)의 해당 딕셔너리에 **자신의 실제 구현체**를 추가합니다.

예: `LLMSegmentRecommender`를 완성했을 때

```python
from ai.recommender import LLMSegmentRecommender
RECOMMENDERS = {
    "stub": StubSegmentRecommender,
    "llm": LLMSegmentRecommender,
}
```

위 등록 예시의 `LLMSegmentRecommender`는 **현재 미구현 상태**입니다. 구현·의존성 설정 후에만 선택합니다. 생성자에 설정 인자가 필요하면 팩토리 함수를 등록합니다.

## 4단계: `.env`로 실행 모드 선택

```dotenv
TRANSCRIBER_BACKEND=stub
PREPROCESSOR_BACKEND=stub
ANALYZER_BACKEND=stub
PROJECT_ANALYZER_BACKEND=stub
RECOMMENDER_BACKEND=llm
EDITOR_BACKEND=stub
```

```powershell
python -m streamlit run src/ui/app.py
```

`.env` 설정 우선순위: PowerShell/운영체제 환경변수 → `.env` → 기본 `stub`.


## 작업자에 관한 주의

단일 프로세스 `ThreadPoolExecutor(max_workers=1)`과 파일 기반 작업 상태를 사용합니다. Streamlit 스크립트 재실행 시에는 `st.cache_resource`로 서비스를 재사용합니다. 프로세스 재시작 시 진행 중 작업은 실패 처리하고, 자동 재실행·동시 다중 서버는 지원하지 않습니다.
