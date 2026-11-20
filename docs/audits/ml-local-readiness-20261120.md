# Read-only audit: local RuBERT / SetFit, 2026-11-20

No training, model downloads, database writes or ML configuration changes were performed. Local model loading was tested in memory only.

## Findings

- Host snapshot: `data/models/rubert`, mounted read-only at `/opt/local-ml` in neural-worker.
- Both ML_RUBERT_BASE_PATH and ML_SETFIT_BASE_PATH resolve to `/opt/local-ml/rubert`; application `_base_path` validation passes for both engines.
- Snapshot includes config.json, model.safetensors (117529600 bytes), tokenizer.json/config/vocabulary, modules.json, sentence_bert_config.json and pooling config.
- HF_HUB_OFFLINE, TRANSFORMERS_OFFLINE and HF_DATASETS_OFFLINE are enabled in neural-worker.
- Installed: torch 2.15.0+cpu, transformers 5.23.0, setfit 1.2.0, sentence-transformers 5.7.0, datasets 4.8.5, accelerate 1.16.0.
- AutoTokenizer and AutoModel load successfully with local_files_only=True; BERT hidden size 312.
- SetFitModel loads successfully with local_files_only=True on CPU. Missing model_head.pkl initializes an untrained classification head, expected for a base encoder; this is not a trained classifier.
- Loading the base encoder reports unused pretraining-head weights. No loading failure occurred.
- Neural worker is configured ML_NEURAL_ONLY=true, 2 CPUs and 5 GiB memory. Actual training throughput and peak memory were NOT tested.
- API and ordinary worker have no base-weight mount. Base-model training readiness applies to neural-worker, not every backend container.
- Database read-only snapshot: 3 inactive TF-IDF models, 1 inactive RuBERT model, no SetFit models; one historical completed ml_train job. No active classifier was present.

## Conclusion

Local dependency/path/encoder-loading prerequisites pass for SetFit and RuBERT in neural-worker. This is NOT proof of successful end-to-end training: dataset balance, training API compatibility, quality gates and resource usage remain unverified. No settings were changed to remedy or bypass limitations.
