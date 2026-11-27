"""Predict with active global TF-IDF and independent per-category classifiers."""


def infer_models(active, text):
    from app.ml import infer
    from app.ml_engines import infer_binary

    predictions, errors = [], []
    for model in active:
        try:
            if model.engine == "tfidf":
                if model.category_id is not None:
                    raise ValueError("TF-IDF model must be global")
                for prediction in infer(model.artifact, text):
                    predictions.append(
                        {
                            **prediction,
                            "model_id": model.id,
                            "engine": "tfidf",
                        }
                    )
            elif model.engine in {"setfit", "rubert"} and model.category_id:
                category = model.category_id
                threshold = float(model.metrics["threshold"])
                prediction = infer_binary(model.artifact, text, category, threshold)
                predictions.append({**prediction, "model_id": model.id, "engine": model.engine})
            else:
                raise ValueError("Invalid ML model metadata")
        except Exception as exc:
            errors.append(
                {
                    "model_id": model.id,
                    "engine": model.engine,
                    "category_id": model.category_id,
                    "error": type(exc).__name__,
                }
            )
    # Independent methods retain separate evidence; never average their scores.
    return predictions, errors
