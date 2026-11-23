# MICE synthetic 350 EML holdout

**For evaluation only — never train on this holdout.** 350 synthetic messages and an independent author-defined semantic ground truth manifest. No expert review is claimed. No real credentials, domains, or personal information.

- `eml/`: 350 complete EML files. First 300 are byte-for-byte Git blob reuse from `../benchmark-300-v2/eml/` with original `MF300-0001..0300` identities. Additional 50 use IDs `MF350-0301..0350`.
- `manifest.jsonl`: 350 rows mapping relative EML paths and expected semantic category labels.
- Added cohorts: control=10, pii=10, commercial=10, safety=8, secrets=6, mixed=6.
- 10 new MIME attachments: 6 high-contrast bitmap PNG images for OCR and 4 native text PDF documents. Each row has `attachment_visible_text` where applicable. Text content in images is English identifiers/numbers and an OCR watermark. The 300 legacy messages already include other formats including DOCX/XLSX.
- Existing and new labels are independent from MICE detectors. Some synthetic examples intentionally have ambiguous context; evaluate with manual review of disagreements.

## Evaluation

Run this set against a fresh isolated database; record the exact Git commit, detectors, rulepacks, OCR backend, policy configuration and ML/LLM versions. Import a pilot of 5 then batches of 50. Match `Message-ID` or `X-MICE-Benchmark`. Compute per-category TP/FP/FN, precision/recall/F1, micro/macro scores, strict multilabel exact match and separate extraction metrics. Group errors by `MF300` vs `MF350`, scenario and attachment type. Do not treat policy incident outcomes as identical to semantic category labels. Ground truth is synthetic scenario-level, not production performance validation.

### New image/PDF cases

- MF350-0304: `fixture-304.png`, text `PUBLIC TEST`
- MF350-0308: `fixture-308.pdf`, text `PUBLIC OFFER`
- MF350-0311: `fixture-311.png`, text `INN 7707083893`
- MF350-0316: `fixture-316.pdf`, text `PASSPORT 4510123456`
- MF350-0319: `fixture-319.png`, text `INN 7707083893`
- MF350-0324: `fixture-324.pdf`, text `PRIVATE BUDGET 2450000`
- MF350-0327: `fixture-327.png`, text `PRIVATE BUDGET`
- MF350-0335: `fixture-335.png`, text `SABOTAGE TEST`
- MF350-0340: `fixture-340.pdf`, text `CREDENTIAL TEST`
- MF350-0348: `fixture-348.png`, text `PASSPORT 4510123456`

Original 300-case generation details are in `../benchmark-300-v2/README.md`.

## Pre-evaluation corrections

Seven new attachments were aligned with their declared scenarios before running MICE; category labels were not tuned. Control 0308 now contains PUBLIC OFFER instead of a passport. See manifest attachment_visible_text for authoritative corrected text. Legacy 300 EML remain byte-identical. Author labels remain provisional, not independently adjudicated.
