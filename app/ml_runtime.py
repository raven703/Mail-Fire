"""Predict with active global TF-IDF and independent per-category classifiers."""

def infer_active(session, text):
    from sqlalchemy import select

    from app.models import MLModel

    return infer_models(list(session.scalars(select(MLModel).where(MLModel.active.is_(True)))), text)


def infer_models(active, text):
    from app.ml import infer
    from app.ml_engines import infer_binary

    global_predictions, custom_predictions, errors = {}, {}, []
    for model in active:
        try:
            if model.engine == "tfidf":
                if model.category_id is not None:
                    raise ValueError("TF-IDF model must be global")
                for prediction in infer(model.artifact, text):
                    global_predictions[prediction["category"]] = {
                        **prediction,
                        "model_id": model.id,
                        "engine": "tfidf",
                    }
            elif model.engine in {"setfit", "rubert"} and model.category_id:
                category = model.category_id
                threshold = float(model.metrics["threshold"])
                prediction = infer_binary(model.artifact, text, category, threshold)
                custom_predictions[category] = {**prediction, "model_id": model.id, "engine": model.engine}
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
    # A specialized model always replaces the global classifier for its category.
    return list({**global_predictions, **custom_predictions}.values()), errors
