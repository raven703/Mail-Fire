"""ML publication and deployment configuration are independent."""
from pipeline.inference import enabled
from records.models import MLModel


def classify_ml_status(total, published, inference_enabled):
    if not total:
        return "Нет модели"
    if not published:
        return "Не опубликована"
    if not inference_enabled:
        return "Отключён"
    return "Включён"


def ml_status():
    models = MLModel.objects.all()
    total = models.count()
    published = models.filter(active=True)
    active = list(published.values("name", "engine"))
    for model in active:
        model["engine_label"] = {
            "tfidf": "TF-IDF / Logistic Regression", "setfit": "SetFit", "rubert": "RuBERT-tiny2",
        }.get(model["engine"], model["engine"])
    gate = enabled("ml")
    return {
        "status_label": classify_ml_status(total, len(active), gate),
        "total_count": total,
        "published_count": len(active),
        "published_models": active,
        "inference_enabled": gate,
        "available": bool(active),
        "enabled": bool(active) and gate,
    }
