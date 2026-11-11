import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai.analyzer import LLMContentAnalyzer
from ai.config import AISettings, AIFallbackPolicy
from ai.preprocessing import AITranscriptPreprocessor
from ai.providers.gemini import GeminiProcessingError, GeminiTranscriptRefiner, _generation_options
from application.config import Settings
from bootstrap import create_application
from core.models import Project, VideoAsset, new_id


def fake_gemini():
    def generate(**kwargs):
        prompt = kwargs['contents']
        if '교정 대상:\n' in prompt:
            result = json.loads(prompt.split('교정 대상:\n', 1)[1])
        else:
            payload = json.loads(prompt.split('입력 JSON:\n', 1)[1])
            result = {'summary': '테스트 요약', 'topics': [{
                'title': '테스트 주제', 'description': '자막 기반 테스트',
                'processed_segment_ids': [s['id'] for s in payload['segments']],
            }]}
        return SimpleNamespace(text=json.dumps(result, ensure_ascii=False))
    return SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=generate)))


def test_real_provider_cache_and_setting_invalidation(tmp_path):
    service = create_application(Settings(runtime_dir=tmp_path))
    client = fake_gemini()
    ai = AISettings(fallback=AIFallbackPolicy.RAISE, preprocessing_concurrency=1)
    service.preprocessor = AITranscriptPreprocessor(settings=ai, gemini_client=client)
    service.analyzer = LLMContentAnalyzer(settings=ai, gemini_client=client)
    try:
        project = service.create_project()
        vid = new_id()
        video = VideoAsset(
            id=vid, project_id=project.id, filename='sample.mp4',
            source_path=service.store.video_dir(project.id, vid) / 'source.mp4',
            duration_ms=10000, sha256='0' * 64, has_audio=True,
        )
        service.store.save_video(video)
        video.source_path.touch()
        service.store.save_project(Project(id=project.id, title=project.title, video_ids=(vid,)))
        service.transcriber.transcribe = Mock(wraps=service.transcriber.transcribe)
        first = service.prepare_video(project.id, vid)
        assert client.models.generate_content.call_count == 2
        assert service.prepare_video(project.id, vid) == first
        assert client.models.generate_content.call_count == 2
        # 동시 요청 수 변경만으로는 결과 캐시를 무효화하지 않습니다.
        service.preprocessor = AITranscriptPreprocessor(settings=replace(ai, preprocessing_concurrency=3), gemini_client=client)
        assert service.prepare_video(project.id, vid) == first
        assert client.models.generate_content.call_count == 2
        # 추론 설정 변경 시 전처리와 후속 분석을 갱신합니다.
        service.preprocessor = AITranscriptPreprocessor(settings=replace(ai, preprocessing_thinking_level='medium'), gemini_client=client)
        assert service.prepare_video(project.id, vid).id != first.id
        assert client.models.generate_content.call_count == 4
        service.transcriber.transcribe.assert_called_once()
    finally:
        service.close()


def test_short_aliases_preserve_real_ids_and_timestamps():
    from core.models import Transcript, TranscriptSegment
    client = fake_gemini()
    original_id = new_id()
    transcript = Transcript(id=new_id(), video_id=new_id(), transcriber_version='test', segments=(
        TranscriptSegment(id=original_id, start_ms=1234, end_ms=2500, text='내용 보존'),
    ))
    processor = AITranscriptPreprocessor(settings=AISettings(), gemini_client=client)
    output = processor.preprocess(transcript)
    call = client.models.generate_content.call_args.kwargs
    payload = json.loads(call['contents'].split('교정 대상:\n', 1)[1])
    assert payload['segments'][0]['id'] == '0'
    assert original_id not in call['contents']
    assert output.segments[0].source_segment_ids == (original_id,)
    assert (output.segments[0].start_ms, output.segments[0].end_ms) == (1234, 2500)
    assert call['config']['thinking_config']['thinking_level'] == 'LOW'
    assert call['config']['automatic_function_calling']['disable'] is True


def test_unknown_alias_is_rejected():
    from core.models import ProcessedSegment
    client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(return_value=SimpleNamespace(
        text=json.dumps({'segments': [{'id': 'wrong', 'text': '내용'}]}),
    ))))
    refiner = GeminiTranscriptRefiner(None, 'test', client)
    with pytest.raises(GeminiProcessingError):
        refiner.refine((ProcessedSegment(id='real', start_ms=0, end_ms=1000, text='내용', source_segment_ids=('s',)),))


def test_model_options_do_not_send_unsupported_thinking_to_other_models():
    assert 'thinking_config' not in _generation_options('custom-model', 'low')
    assert 'thinking_config' not in _generation_options('gemini-3.8-flash', 'default')


@pytest.mark.parametrize('changes', [
    {'preprocessing_thinking_level': 'minimal'}, {'analysis_thinking_level': 'bad'},
    {'preprocessing_batch_segments': 0}, {'preprocessing_batch_characters': 20001},
    {'gemini_timeout_seconds': 0},
])
def test_invalid_optimization_settings(changes):
    with pytest.raises(ValueError):
        AISettings(**changes)


def test_whisper_uses_downloaded_model_without_revision_request(monkeypatch):
    from processing.whisper import WhisperTranscriber
    from faster_whisper import utils
    import faster_whisper
    resolve = Mock(return_value='/cached/whisper-small')
    constructor = Mock()
    monkeypatch.setattr(utils, 'download_model', resolve)
    monkeypatch.setattr(faster_whisper, 'WhisperModel', constructor)
    monkeypatch.setattr(WhisperTranscriber, '_model_cache', {})
    transcriber = WhisperTranscriber(model_size='small', device='cpu', compute_type='int8')
    transcriber._load_model()
    resolve.assert_called_once_with('small', local_files_only=True)
    assert constructor.call_args.args == ('/cached/whisper-small',)
    transcriber._load_model()
    constructor.assert_called_once()
