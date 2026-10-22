from types import SimpleNamespace

from app.services.zhipu_emohaa_service import ZhipuEmohaaService


def test_invalid_input_returns_default_tags():
    service = ZhipuEmohaaService()
    out = service._analyze_emotion_sync("！！！。。。", retry=1)
    assert out == service.DEFAULT_EMOTION_TAGS


def test_parse_and_normalize_six_dimensions():
    service = ZhipuEmohaaService()
    raw = {"joy": 0.2, "sadness": 0.2, "neutral": 0.2, "fear": 0.2, "anxiety": 0.1, "anger": 0.1}
    out = service._normalize_emotion_tags(raw)
    assert set(out.keys()) == {"joy", "sadness", "neutral", "fear", "anxiety", "anger"}
    assert all(0.0 <= v <= 1.0 for v in out.values())
    assert abs(sum(out.values()) - 1.0) < 0.02


def test_parse_fenced_json_payload():
    service = ZhipuEmohaaService()
    payload = """```json
{"joy":0.1,"sadness":0.2,"neutral":0.5,"fear":0.1,"anxiety":0.05,"anger":0.05}
```"""
    out = service._parse_emotion_payload(payload)
    assert out["neutral"] > 0.0
    assert abs(sum(out.values()) - 1.0) < 0.02


def test_retry_once_then_success():
    service = ZhipuEmohaaService()

    class DummyCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("timeout")
            content = '{"joy":0.0,"sadness":0.4,"neutral":0.2,"fear":0.2,"anxiety":0.1,"anger":0.1}'
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
            )

    completions = DummyCompletions()
    # This test explicitly exercises the SDK transport; optional SDK discovery
    # must not silently select the real HTTP transport in a lightweight runtime.
    service.provider = "zai_sdk"
    service.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    out = service._analyze_emotion_sync("我最近很焦虑也有点难过", retry=1)
    assert completions.calls == 2
    assert out["sadness"] > 0
    assert out["anxiety"] > 0
    assert abs(sum(out.values()) - 1.0) < 0.02


def test_http_transport_retries_without_optional_sdk(monkeypatch):
    service = ZhipuEmohaaService()
    service.provider = "http"
    calls = []
    def fake_completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise TimeoutError("synthetic timeout")
        return '{"joy":0.1,"sadness":0.3,"neutral":0.2,"fear":0.1,"anxiety":0.2,"anger":0.1}'
    monkeypatch.setattr(service, "_http_chat_completion", fake_completion)
    out = service._analyze_emotion_sync("合成测试：最近感到焦虑", retry=1)
    assert len(calls) == 2
    assert abs(sum(out.values()) - 1.0) < 0.02
