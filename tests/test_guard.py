import asyncio
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import types
sys.modules.setdefault("requests", types.ModuleType("requests"))
fake_httpx = types.ModuleType("httpx")
fake_httpx.AsyncClient = object
fake_httpx.Client = object
sys.modules.setdefault("httpx", fake_httpx)

from test_savant.guard import Guard, InputGuard, OutputGuard

class DummyScanner:
    def __init__(self, requires_prompt=False):
        self._requires_input_prompt = requires_prompt

    def to_dict(self, request_only=False):
        return {"name": "Dummy", "params": {}}

class DummyResponse:
    def __init__(self):
        self.headers = {"Content-Type": "application/json"}
    def json(self):
        return {
            "sanitized_prompt": "",
            "is_valid": True,
            "scanners": {},
            "validity": {}
        }
    def raise_for_status(self):
        pass
    @property
    def text(self):
        return "ok"

class DummyAsyncClient:
    def __init__(self, *a, **kw):
        self.request_kwargs = None
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def request(self, *args, **kwargs):
        self.request_kwargs = kwargs
        return DummyResponse()


def test_scanners_to_dict_requires_scanner():
    g = Guard("k", "p")
    try:
        g._scanners_to_dict([])
    except ValueError:
        pass
    else:
        assert False, "expected ValueError"


def test_prepare_request_json_includes_output():
    g = Guard("k", "p")
    data = g._prepare_request_json("p", "id", ["s"], output="out")
    assert data["output"] == "out"


def test_request_api_does_not_mutate_files(monkeypatch):
    g = Guard("k", "p")
    files = [("f", ("name", b"d", "text/plain"))]

    async def run():
        monkeypatch.setattr("httpx.AsyncClient", DummyAsyncClient)
        await g.request_api("http://example.com", data="meta", files=files, async_mode=True)
    asyncio.run(run())
    assert files == [("f", ("name", b"d", "text/plain"))]


def test_output_guard_prompt_requirement(monkeypatch):
    og = OutputGuard("k", "p")
    og.add_scanner(DummyScanner(requires_prompt=True))

    def dummy_make_request(*a, **kw):
        return "ok"
    monkeypatch.setattr(Guard, "make_request", dummy_make_request)

    try:
        og.scan(prompt=None, output="out")
    except ValueError:
        pass
    else:
        assert False, "expected ValueError when prompt missing"

    # with prompt provided
    assert og.scan(prompt="prompt", output="out") == "ok"


def test_input_guard_errors(monkeypatch):
    ig = InputGuard("k", "p")

    try:
        ig.scan(prompt="", files=None)
    except ValueError:
        pass
    else:
        assert False, "expected ValueError when no scanners"

    ig.add_scanner(DummyScanner())
    def dummy_make_request(*a, **kw):
        return "ok"
    monkeypatch.setattr(Guard, "make_request", dummy_make_request)

    try:
        ig.scan(prompt="", files=None)
    except ValueError:
        pass
    else:
        assert False, "expected ValueError when no prompt and files"

    assert ig.scan(prompt="hello") == "ok"

def test_input_guard_empty_prompt_and_files(monkeypatch):
    ig = InputGuard("k", "p")
    ig.add_scanner(DummyScanner())
    def dummy_make_request(*a, **kw):
        return "should not be called"
    monkeypatch.setattr(Guard, "make_request", dummy_make_request)
    # Both prompt and files empty
    try:
        ig.scan(prompt="", files=[])
    except ValueError as e:
        assert "Either prompt or files must be provided" in str(e)
    else:
        assert False, "expected ValueError when both prompt and files are empty"

def test_input_guard_empty_files(monkeypatch):
    ig = InputGuard("k", "p")
    ig.add_scanner(DummyScanner())
    def dummy_make_request(*a, **kw):
        return "ok"
    monkeypatch.setattr(Guard, "make_request", dummy_make_request)
    # Prompt provided, files empty
    assert ig.scan(prompt="test", files=[]) == "ok"

def test_output_guard_empty_output_and_files(monkeypatch):
    og = OutputGuard("k", "p")
    og.add_scanner(DummyScanner())
    def dummy_make_request(*a, **kw):
        return "should not be called"
    monkeypatch.setattr(Guard, "make_request", dummy_make_request)
    # Both output and files empty
    try:
        og.scan(prompt="prompt", output=None, files=None)
    except ValueError as e:
        assert "Either output or files must be provided" in str(e)
    else:
        assert False, "expected ValueError when both output and files are empty"

def test_output_guard_empty_files(monkeypatch):
    og = OutputGuard("k", "p")
    og.add_scanner(DummyScanner())
    def dummy_make_request(*a, **kw):
        return "ok"
    monkeypatch.setattr(Guard, "make_request", dummy_make_request)
    # Output provided, files empty
    assert og.scan(prompt="prompt", output="output", files=[]) == "ok"
