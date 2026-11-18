"""Materialize PaddleOCR 2.x CPU weights at image build, never during parsing."""

from paddleocr import PaddleOCR

PaddleOCR(
    lang="ru",
    use_gpu=False,
    use_angle_cls=False,
    show_log=False,
    enable_mkldnn=False,
    cpu_threads=1,
    det_model_dir="/opt/ocr-models/paddle/det",
    rec_model_dir="/opt/ocr-models/paddle/rec",
    cls_model_dir="/opt/ocr-models/paddle/cls",
)
