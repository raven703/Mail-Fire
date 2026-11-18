import io

from app.config import settings


def test_real_rapidocr_image(monkeypatch):
    from PIL import Image, ImageDraw, ImageFont

    from app.ocr import recognize

    monkeypatch.setattr(settings(), "ocr_backend", "rapidocr")
    image = Image.new("RGB", (1400, 180), "white")
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    ImageDraw.Draw(image).text((20, 40), "CONFIDENTIAL FINANCIAL REPORT 2026", fill="black", font=font)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    text, metadata = recognize(stream.getvalue())
    assert "FINANCIAL" in text
    assert metadata["blocks"][0]["confidence"] > 0.8
    assert len(metadata["blocks"][0]["box"]) == 4


def test_real_ocr_sandbox(monkeypatch):
    from PIL import Image, ImageDraw, ImageFont

    from app.sandbox import call

    monkeypatch.setattr(settings(), "ocr_backend", "rapidocr")
    image = Image.new("RGB", (1200, 160), "white")
    ImageDraw.Draw(image).text(
        (20, 40),
        "SECRET DOCUMENT 2026",
        fill="black",
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40),
    )
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    result = call("extract", stream.getvalue(), "scan.png")
    assert result["status"] == "ANALYZED"
    assert "SECRET" in result["text"]
