"""OCR of scanned pages with a vision model: transcripts, parsing, the comparison with EasyOCR (no network)."""

from agro.common.providers import Completion
from agro.corpus import vision_ocr
from agro.corpus.ocr_compare import compare, numbers

PAGE = """<!-- ocr: google/gemini-2.5-flash, prompt ocr/v1, 200 dpi, d page 3 -->
## Агрометеорологічні умови

У першій декаді вересня переважала тепла погода.
Опади були локальними.

- Західний регіон
- Південний регіон

| Область | Опади, мм | Норма, % |
|---|---|---|
| Одеська | 12 | -35 |
| Херсонська | [?] | +4 |
"""


def test_markdown_page_becomes_blocks():
    blocks = vision_ocr.markdown_to_blocks(vision_ocr._body(PAGE), 3)
    assert [b.kind for b in blocks] == ["heading", "text", "text", "text", "table"]
    assert blocks[1].text == "У першій декаді вересня переважала тепла погода. Опади були локальними."
    assert blocks[2].text == "- Західний регіон"
    assert blocks[4].rows == [["Область", "Опади, мм", "Норма, %"], ["Одеська", "12", "-35"], ["Херсонська", "[?]", "+4"]]
    assert all(b.ocr and b.page == 3 for b in blocks)


class FakePage:
    class Pix:
        def tobytes(self, fmt):
            return b"png"

    def get_pixmap(self, dpi):
        return self.Pix()


def test_transcript_is_written_once_and_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(vision_ocr, "OCR_DIR", tmp_path)
    calls = []

    class FakeProvider:
        model = "google/gemini-2.5-flash"

        def complete(self, messages, schema, sampling, max_tokens):
            calls.append(messages)
            return Completion("```markdown\n## Заголовок\n\nТекст сторінки.\n```", 1000, 50, "stop")

        def cost_usd(self, c):
            return 0.001

    r = vision_ocr.VisionOcr()
    r._provider = FakeProvider()
    blocks = r.read_page(FakePage(), 5, language="uk", doc_id="d")
    assert [b.text for b in blocks] == ["Заголовок", "Текст сторінки."]       # the code fence is removed
    saved = (tmp_path / "d" / "page-005.md").read_text(encoding="utf-8")
    assert saved.startswith(f"<!-- ocr: google/gemini-2.5-flash, prompt ocr/{vision_ocr.PROMPT_VERSION}, 200 dpi, d page 5 -->")
    content = calls[0][0]["content"]
    assert "Ukrainian" in content[0]["text"] and content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    vision_ocr.VisionOcr().read_page(FakePage(), 5, doc_id="d")           # no provider: read from the file
    assert len(calls) == 1


def test_text_response_format_sends_no_schema(monkeypatch):
    from agro.common.providers import OpenAICompatibleProvider

    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    cfg = {"model": "m", "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}
    assert OpenAICompatibleProvider({**cfg, "response_format": "text"})._response_format({}) is None
    assert OpenAICompatibleProvider(cfg)._response_format({})["type"] == "json_schema"


def test_comparison_with_easyocr():
    vocab = {"опади", "були", "області", "одеській"}
    easy = "Опади буди в Одеськіи області 12 35 4"
    vision = "Опади були в Одеській області 12 -35 +4 7.5"
    c = compare(easy, vision, vocab)
    assert c["known_%"][1] > c["known_%"][0]
    assert c["numbers"] == (3, 4) and c["signed"] == (0, 2)
    assert c["vision_numbers_also_in_easyocr_%"] == 75.0 and c["only_vision"] == ["7.5"]
    assert numbers("−3,5 і +12") == ["-3.5", "+12"]
    assert numbers("1295-1325 мм, 20-25 °С") == ["1295", "1325", "20", "25"]        # ranges, not signs
    assert numbers("| **5 508** | - 17 | + 35 | – 9 |") == ["5", "508", "-17", "+35", "-9"]   # JRC: the sign apart


def test_runaway_table_separator(tmp_path, monkeypatch):
    """A printed rule of dashes copied without end: a run of dashes is cut back; a cut answer is an error."""
    monkeypatch.setattr(vision_ocr, "OCR_DIR", tmp_path)

    class Looping:
        model = "m"

        def __init__(self, content, reason):
            self.c = Completion(content, 1000, 100, reason)

        def complete(self, *a, **k):
            return self.c

        def cost_usd(self, c):
            return 0.0

    r = vision_ocr.VisionOcr()
    r._provider = Looping("| a | b |\n|" + "-" * 60 + "|---|\n| 1 | 2 |", "stop")
    assert r.read_page(FakePage(), 1, doc_id="d")[0].rows == [["a", "b"], ["1", "2"]]
    r._provider = Looping("| a | b |\n|" + "-" * 5000, "length")
    import pytest
    with pytest.raises(RuntimeError, match="looped copying a printed rule"):
        r.read_page(FakePage(), 2, doc_id="d")


def test_whole_scan_without_imprint_pages():
    from agro.corpus.registry import DocMeta

    base = dict(doc_id="d", format="pdf", language="uk", source="s", title="T", period="2023-09-d1",
                effective="2023-09-10", topic="agromet", url="u")
    m = DocMeta(**base, ocr="all except:2,9")
    assert m.ocr_pages(9) == {1, 3, 4, 5, 6, 7, 8} and m.ocr_whole_scan
    assert not DocMeta(**base, ocr="pages:12").ocr_whole_scan and DocMeta(**base, ocr="all").ocr_pages(2) == {1, 2}
