"""Real CPU OCR adapters. No model download is allowed during parsing."""

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def engine():
    backend = settings().ocr_backend
    if backend == "rapidocr":
        from pathlib import Path

        import rapidocr
        from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

        return RapidOCR(
            params={
                "Global.log_level": "critical",
                "Rec.model_path": str(
                    Path(rapidocr.__file__).parent / "models" / "cyrillic_PP-OCRv5_rec_mobile.onnx"
                ),
                "Rec.lang_type": LangRec.CYRILLIC,
                "Rec.ocr_version": OCRVersion.PPOCRV5,
                "Rec.model_type": ModelType.MOBILE,
                "EngineConfig.onnxruntime.intra_op_num_threads": 1,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
            }
        )
    if backend == "paddleocr":
        from paddleocr import PaddleOCR

        return PaddleOCR(
            lang="ru",
            use_gpu=False,
            use_angle_cls=False,
            show_log=False,
            enable_mkldnn=False,
            cpu_threads=1,
            det_model_dir=settings().ocr_model_root + "/paddle/det",
            rec_model_dir=settings().ocr_model_root + "/paddle/rec",
            cls_model_dir=settings().ocr_model_root + "/paddle/cls",
        )
    raise RuntimeError("OCR backend disabled or unavailable")


def recognize(data, page=1):
    if settings().ocr_backend == "rapidocr":
        result = engine()(data)
        blocks = [
            {"text": str(text), "confidence": float(score), "box": box.tolist(), "page": page}
            for text, score, box in zip(
                result.txts or [], result.scores or [], result.boxes if result.boxes is not None else []
            )
        ]
    else:
        import io

        import numpy as np
        from PIL import Image

        results = engine().ocr(np.array(Image.open(io.BytesIO(data)).convert("RGB")), cls=False)
        blocks = []
        for result in results:
            for box, (text, score) in result or []:
                blocks.append(
                    {
                        "text": str(text),
                        "confidence": float(score),
                        "box": np.asarray(box).tolist(),
                        "page": page,
                    }
                )
    return "\n".join(b["text"] for b in blocks), {"backend": settings().ocr_backend, "blocks": blocks}
