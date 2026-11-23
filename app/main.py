from app.accounts_api import router as accounts_router
from app.preview_api import router as preview_router
from app.admin_api import router as admin_router
from app.api import app
from app.catalog_api import router as catalog_router
from app.categories_api import router as categories_router
from app.llm_api import router as llm_router
from app.ml_api import router
from app.ml_datasets_api import router as datasets_router
from app.monitoring import router as monitoring_router
from app.reference_api import router as reference_router
from app.retention_api import router as retention_router
from app.rulepacks_api import router as rulepacks_router
from app.semantic_api import router as semantic_router
from app.workspace_api import router as workspace_router

app.include_router(router)
app.include_router(llm_router)
app.include_router(datasets_router)
app.include_router(admin_router)
app.include_router(accounts_router)
app.include_router(preview_router)
app.include_router(reference_router)
app.include_router(retention_router)
app.include_router(monitoring_router)
app.include_router(semantic_router)
app.include_router(workspace_router)
app.include_router(catalog_router)
app.include_router(categories_router)


app.include_router(rulepacks_router)
