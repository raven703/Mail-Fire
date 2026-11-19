"""Admin-only LLM controls, stored without tokens or raw emails."""
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.api import admin, db
from app.models import Audit, Category, Setting
from app.llm_analyzer import DEFAULTS
from sqlalchemy import select

router = APIRouter(prefix="/api/llm", tags=["LLM analyzer"])


class LLMSettings(BaseModel):
    enabled: bool = False
    provider: Literal["local", "openai"] = "local"
    base_url: str = Field(default="", max_length=2048)
    model: str = Field(default="model.gguf", min_length=1, max_length=160)
    routing: Literal["uncertain", "selected", "both"] = "uncertain"
    categories: list[str] = Field(default_factory=list, max_length=50)
    min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    timeout_seconds: int = Field(default=30, ge=2, le=120)
    max_chars: int = Field(default=8000, ge=200, le=20000)
    allow_external_content: bool = False


@router.get("/settings")
def read_settings(account=Depends(admin), session=Depends(db)):
    row = session.get(Setting, "llm_analyzer")
    config = {**DEFAULTS, **(row.value if row else {})}
    config["base_url"] = config["base_url"] if config["provider"] == "openai" else "http://llm:8080/v1"
    config["api_key_env"] = "MAILFIRE_LLM_API_KEY"
    return config


@router.put("/settings")
def update_settings(body: LLMSettings, account=Depends(admin), session=Depends(db)):
    if body.provider == "openai":
        parsed = urlsplit(body.base_url.strip())
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise HTTPException(422, "Внешний API должен использовать HTTPS без авторизации в URL")
        if body.enabled and not body.allow_external_content:
            raise HTTPException(422, "Подтвердите разрешение на передачу содержимого внешнему сервису")
    ids = set(body.categories)
    if len(ids) != len(body.categories):
        raise HTTPException(422, "Дублирующиеся категории")
    actual = set(session.scalars(select(Category.id).where(Category.id.in_(ids), Category.active.is_(True))))
    if actual != ids:
        raise HTTPException(422, "Неизвестная или неактивная категория")
    data = body.model_dump()
    if body.provider == "local":
        data["base_url"] = "http://llm:8080/v1"
        data["allow_external_content"] = False
    row = session.get(Setting, "llm_analyzer")
    if not row:
        row = Setting(key="llm_analyzer", value={})
        session.add(row)
    row.value = data
    session.add(Audit(
        actor=account.id, action="llm_configuration", target="llm_analyzer",
        details={"provider": body.provider, "enabled": body.enabled,
                 "routing": body.routing, "categories": body.categories,
                 "external_approved": data["allow_external_content"]},
    ))
    session.commit()
    return {**data, "api_key_env": "MAILFIRE_LLM_API_KEY"}
