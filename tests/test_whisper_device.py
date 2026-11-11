import sys
from types import SimpleNamespace

import pytest

from processing.whisper import WhisperTranscriber


@pytest.mark.parametrize(('system', 'machine', 'supported', 'expected'), [
    ('Darwin', 'arm64', True, ('mps', 'float32')),
    ('Darwin', 'arm64', False, ('cpu', 'int8')),
    ('Darwin', 'x86_64', True, ('cpu', 'int8')),
    ('Windows', 'AMD64', True, ('cpu', 'int8')),
])
def test_auto_device(monkeypatch, system, machine, supported, expected):
    monkeypatch.setattr('processing.whisper.platform.system', lambda: system)
    monkeypatch.setattr('processing.whisper.platform.machine', lambda: machine)
    def compute_types(device):
        if not supported:
            raise ValueError('unsupported device')
        return {'float32'}
    monkeypatch.setitem(sys.modules, 'ctranslate2', SimpleNamespace(get_supported_compute_types=compute_types))
    transcriber = WhisperTranscriber(device='auto', compute_type='auto')
    assert (transcriber.device, transcriber.compute_type) == expected


def test_explicit_cpu_is_preserved():
    transcriber = WhisperTranscriber(device='cpu', compute_type='int8')
    assert (transcriber.device, transcriber.compute_type) == ('cpu', 'int8')
