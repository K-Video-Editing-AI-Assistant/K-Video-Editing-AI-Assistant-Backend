# 담당자 개발·테스트 2단계 가이드

[← 시작 가이드](START_HERE.md) · [담당자별 업무](ROLE_IMPLEMENTATION_MANUAL.md) · [입출력 계약](INPUT_OUTPUT_CONTRACT_V1.md)

**원칙: 모듈을 완성하기 전까지는 독립 테스트에 집중합니다. `bootstrap.py` 등록이나 화면 연동은 필수가 아닙니다.**

## 1단계 — 내 모듈 구현 및 독립 테스트 (먼저 해야 할 일)

1. 자기 [역할 페이지](ROLE_IMPLEMENTATION_MANUAL.md)에서 **입력 모델 / 공개 메서드 / 반환 모델 / 수정 파일**을 확인합니다.
2. 기존 `stub.py`는 유지하고, 자기 실제 구현 파일에 알고리즘을 작성합니다.
3. 선행 모듈이 미완성이어도 `tests/fixtures/contract_samples.py`에서 입력을 가져옵니다.
4. `MyImplementation().public_method(...)`를 **직접 호출**하는 단위·계약 테스트를 작성합니다. 이때 `bootstrap.py`, `Workflow`, Streamlit에 연결할 필요는 없습니다.
5. **정상 결과, 빈 결과, 실패 상황**을 테스트하고 실제 품질도 확인합니다. 수정→테스트를 반복합니다.
6. Output은 `core/models.py`의 Pydantic 객체여야 하고, 참조 ID / 밀리초 시간 / 버전 규칙을 지켜야 합니다.

| 담당 | 독립 테스트에 사용할 입력 | 호출할 공개 메서드 | 반환 형식 |
|---|---|---|---|
| 음성 인식 | `sample_video()` + 실제 발화 샘플 영상 | `transcribe(video)` | `Transcript` |
| 내용 분석 | `sample_transcript()` | `analyze(transcript)` | `VideoAnalysis` |
| 검색·추천 | `sample_request()`, `sample_transcript()`, `sample_analysis(transcript)` | `recommend(request, transcript, analysis)` | `RecommendationResult` |
| 영상 편집 | `sample_video()`, `sample_approved_plan()` | `render(video, plan, output_path)` | `RenderResult` + 실제 MP4 |
| UI | 모든 백엔드 `stub` + `examples/demo.mp4` | `ApplicationService` 호출, 화면 상호작용 | 사용자 흐름·상태 표시 |

**추천 담당 독립 테스트 예시** (자기 구현체를 만들었다는 전제):

```python
from tests.fixtures.contract_samples import sample_request, sample_transcript, sample_analysis
from video_assistant.recommendation.llm import LLMSegmentRecommender

transcript = sample_transcript()
request = sample_request()
analysis = sample_analysis(transcript)

recommender = LLMSegmentRecommender()  # 실제 생성자에 맞춰 설정 전달
result = recommender.recommend(request, transcript, analysis)

assert result.request_id == request.id
assert result.transcript_id == transcript.id
assert result.analysis_id == analysis.id
assert len(result.clips) <= request.max_clips
```

`LLMSegmentRecommender`는 아직 구현되지 않았습니다. 위 코드는 **담당자가 구현한 뒤 작성할 테스트 예시**이며, 실제 생성자·API 모킹 방법은 담당 구현에 맞춰 수정합니다. 별도 API 호출 없는 독립 테스트를 위해 가짜 LLM 응답을 주입하는 것도 권장합니다.

프로젝트에 이미 포함된 참고 테스트:

```powershell
python -m pytest -q tests/contract/test_module_io_contracts.py
python -m pytest -q tests/contract/test_recommender_keyword.py
```

기존 `test_recommender_keyword.py`는 학습용 키워드 추천의 연결 테스트입니다. **자신의 구현에 대한 독립 테스트를 새로 작성해야 합니다.**

### 1단계를 마친 기준

- [ ] 공개 메서드를 직접 호출할 수 있다.
- [ ] 올바른 Pydantic Output과 참조 ID·시간·버전을 반환한다.
- [ ] 정상 / 빈 결과 / 실패 테스트를 통과한다.
- [ ] 선행 담당자의 실제 구현 없이도 테스트된다.
- [ ] 실제 기능의 핵심 품질을 별도 검증했다.

## 2단계 — 모듈이 준비되면 전체 흐름 테스트

**위 1단계를 만족한 뒤에만** 진행합니다.

1. 자신의 **개발 브랜치**에서 `src/video_assistant/bootstrap.py`의 **자기 모듈 레지스트리에만** 구현체(또는 인자 없는 팩토리)를 추가합니다. 등록 자체는 팀장에게 요청할 필요가 없습니다.
2. 내 백엔드만 `real`(예: `llm`)로 선택하고 **다른 미완성 모듈은 `stub`**으로 둡니다.
3. `ApplicationService` → 내 메서드 → Output 검증·저장 → 후속 Stub 단계까지 이어지는 통합 테스트를 수행합니다.
4. Streamlit에서 결과 조회·표시와 실패 상태를 확인합니다. 장시간 작업은 `JobStatus`를 조회합니다.
5. 독립 테스트와 기존 회귀 테스트를 다시 실행합니다.
6. **구현 파일 + 등록 코드 + 테스트 결과**를 함께 PR로 제출합니다. 팀장 및 관련 담당자는 공통 계약과 전체 흐름을 검토합니다.

추천 모듈이 완성된 뒤의 PowerShell 설정 예시:

```powershell
$env:TRANSCRIBER_BACKEND = "stub"
$env:ANALYZER_BACKEND = "stub"
$env:RECOMMENDER_BACKEND = "llm"
$env:EDITOR_BACKEND = "stub"
python -m streamlit run src/video_assistant/ui/app.py
```

위 명령은 **`RECOMMENDERS["llm"]`가 등록되고 필요한 의존성이 설치된 경우에만** 동작합니다. 실제 레지스트리에는 현재 `stub`, `keyword`만 있습니다. 먼저 시험하려면 `RECOMMENDER_BACKEND=keyword`를 사용하세요. 설정 변경 후 Streamlit을 재시작합니다.

```powershell
# 등록 후 내 실제 백엔드용 통합 테스트를 추가해 실행
python -m pytest -q tests/integration/
python -m pytest -q

# 주의: 다음 명령은 환경변수와 무관하게 전부 Stub으로 실행
python scripts/smoke_test.py
```

### 2단계를 마친 기준

- [ ] 내 구현체가 개발 브랜치의 `bootstrap.py`에 등록되어 선택 가능하다.
- [ ] 내 실제 구현 + 다른 모듈 Stub 조합이 정상 동작한다.
- [ ] UI부터 결과 조회까지 확인했고 오류도 표시된다.
- [ ] 전체 자동 테스트가 통과한다.
- [ ] 구현·등록 변경·테스트 내역을 포함한 PR을 제출했다.

## 팀장의 역할

팀장은 **독립 테스트 중인 팀원에게 등록을 요구하지 않습니다.** 팀원은 개발과 첫 통합 테스트를 자신의 브랜치에서 수행합니다. 팀장은 계약 변경을 조율하고, PR에서 `bootstrap.py`의 다른 레지스트리와의 충돌, 입력·출력 정합성, 혼합 실행 결과를 검토한 뒤 `main`에 병합합니다.

## 실패할 때 확인할 것

- **독립 테스트 오류:** 모델 필드, 참조 ID, `VERSION`, 입력 Fixture 또는 실제 구현 내부 오류를 먼저 확인합니다. `bootstrap.py`와 무관합니다.
- **통합 테스트만 실패:** 등록 키, 환경변수, 생성자/팩토리, 모듈 호출 순서, JobStatus·Storage의 검증 실패를 확인합니다.
- **분석/추천 결과가 예상과 다름:** Stub 입력이 실제 영상의 내용과 무관하다는 점, 캐시된 결과인지 확인합니다.
- **영상 편집 검증:** StubVideoEditor는 원본 복사만 합니다. 실제 컷 정확도는 `FFmpegVideoEditor`로 별도 시험해야 합니다.

**세부 Result 필드와 검증:** [Input/Output 계약](INPUT_OUTPUT_CONTRACT_V1.md) · **입출력 JSON 예시:** [샘플](CONTRACT_SAMPLE_OUTPUTS.md) · **연결 원리:** [모듈 연결](MODULE_INTEGRATION_GUIDE.md)
