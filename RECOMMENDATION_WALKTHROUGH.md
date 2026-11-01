# Recommendation 담당자 따라하기

**중요:** 이 문서는 초기 프로젝트에 포함된 학습용 `KeywordSegmentRecommender` 실습입니다. LLM 검색·추천 구현은 아직 없으며, 담당자는 자신의 모듈을 독립 테스트한 뒤 필요할 때 전체 흐름에 등록합니다.

## 실행

프로젝트 루트에서:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
# 처음 한 번 .env.example을 .env로 복사합니다 (OS별 명령은 README 참조).
python -m pytest -q
python -m pytest -q tests/contract/test_recommender_keyword.py
```

시스템에 `ffprobe`가 필요합니다.

## Streamlit에서 키워드 추천 실행

개인 `.env` 파일에서 `RECOMMENDER_BACKEND=keyword`로 변경한 후 실행합니다.

```powershell
python -m streamlit run src/video_assistant/ui/app.py
```

`examples/demo.mp4`를 업로드 → 영상 준비 → `AI 활용` 검색 → 추천 확인하세요. 해당 데모 영상의 자막과 분석 결과는 Stub이므로 추천 근거도 실제 영상 음성과는 관계가 없습니다.

## 자신의 최종 구현 파일

- `src/video_assistant/recommendation/llm.py`: `LLMSegmentRecommender(SegmentRecommender)` 작성
- `tests/contract/test_recommender.py`: 정상 검색/추천 없음/개수 제한/시간 범위/ID 검증/잘못된 LLM 응답/외부 API 실패
- 모델·프롬프트·검색 품질은 담당자가 개선
- 공통 `core/models.py`/`core/interfaces.py`는 팀장 승인 없이 변경하지 않음
- 구현이 완성되면 **담당자가 자신의 브랜치에서** `bootstrap.py`의 `RECOMMENDERS`에 등록하고, Stub/Real 통합 테스트 후 PR 제출

## 학습 파일의 한계

`keyword.py`는 `re.findall()`로 사용자 요청의 단어를 추출하고, 자막/주제 제목에 포함된 단어 개수로 구간을 정렬하는 단순한 규칙 기반 구현입니다. 한국어 형태소 분석, 의미 검색, 문장 문맥, LLM 추론, 하이라이트 조정 등은 처리하지 않습니다.

`smoke_test.py`는 내부에서 기본 Settings를 직접 생성하므로 `RECOMMENDER_BACKEND=keyword`를 설정해도 항상 모든 Stub으로 실행됩니다. **추천 모듈의 실제 교체 여부를 검증할 때는 위 계약 테스트 또는 Streamlit을 사용하세요.**

## 연결과 결과 모델의 상세 안내

[docs/MODULE_INTEGRATION_GUIDE.md](docs/MODULE_INTEGRATION_GUIDE.md)에서 `RecommendationResult` 필드별 계약과 실제 Workflow 호출/저장/계획 생성 과정을 확인하세요. `python scripts/inspect_recommendation_flow.py`로 전체 결과를 출력할 수 있습니다.
