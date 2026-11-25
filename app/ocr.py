"""Real CPU OCR adapters. No model download is allowed during parsing."""

from functools import lru_cache
from importlib.metadata import version
from time import perf_counter

from app.config import settings


@lru_cache(maxsize=1)
def engine():
    backend = settings().ocr_backend
    if backend == "surya":
        from surya.detection import DetectionPredictor
        from surya.recognition import RecognitionPredictor
        return RecognitionPredictor(), DetectionPredictor()
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
    started = perf_counter()
    if settings().ocr_backend == "rapidocr":
        result = engine()(data)
        blocks = [
            {"text": str(text), "confidence": float(score), "box": box.tolist(), "page": page}
            for text, score, box in zip(
                result.txts or [], result.scores or [], result.boxes if result.boxes is not None else []
            )
        ]
    elif settings().ocr_backend == "surya":
        import io
        from PIL import Image
        predictor, detector = engine()
        with Image.open(io.BytesIO(data)) as image:
            result = predictor([image.convert("RGB")], det_predictor=detector, math_mode=False)[0]
        blocks = [{"text": line.text, "confidence": line.confidence,
                   "box": line.polygon, "page": page} for line in result.text_lines]
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
    backend = settings().ocr_backend
    return "\n".join(b["text"] for b in blocks), {
        "backend": backend, "engine": backend, "version": version("surya-ocr" if backend == "surya" else backend),
        "model": {"surya": "detection-2025_05_07/recognition-2025_05_16",
                  "rapidocr": "cyrillic_PP-OCRv5_rec_mobile", "paddleocr": "ru_PP-OCRv3"}[backend],
        "page": page, "seconds": perf_counter() - started, "blocks": blocks,
    }
