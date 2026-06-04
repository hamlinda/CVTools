import pytest

from backend.services.ollama_client import OllamaClient


def test_safe_parse_valid_json():
    text = '{"detections": [{"label": "person", "bbox": [0.1,0.1,0.2,0.2], "confidence": 0.9}]}'
    parsed = OllamaClient._safe_parse_json(text)
    assert "detections" in parsed


def test_safe_parse_embedded_json():
    text = "Model output:\nSome commentary\n{" + '"detections": [1,2,3]}'
    parsed = OllamaClient._safe_parse_json(text)
    assert parsed == {"detections": [1, 2, 3]}


def test_safe_parse_malformed():
    with pytest.raises(ValueError):
        OllamaClient._safe_parse_json("not json at all")
