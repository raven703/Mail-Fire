"""Install language model weights into the immutable image, not runtime storage."""

import urllib.request
from pathlib import Path

import rapidocr
from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

# Model resolver may use a build-user cache. Materialize explicitly into the
# installed dependency so the unprivileged offline parser sees the same weights.
target = Path(rapidocr.__file__).parent / "models" / "cyrillic_PP-OCRv5_rec_mobile.onnx"
if not target.exists():
    urllib.request.urlretrieve(
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx/PP-OCRv5/rec/cyrillic_PP-OCRv5_rec_mobile.onnx",
        target,
    )

RapidOCR(
    params={
        "Rec.lang_type": LangRec.CYRILLIC,
        "Rec.ocr_version": OCRVersion.PPOCRV5,
        "Rec.model_type": ModelType.MOBILE,
        "EngineConfig.onnxruntime.intra_op_num_threads": 1,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    }
)
