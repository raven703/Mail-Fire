from app.admin_api import router as admin_router
from app.api import app
from app.ml_api import router
from app.monitoring import router as monitoring_router
from app.reference_api import router as reference_router
from app.retention_api import router as retention_router

app.include_router(router)
app.include_router(admin_router)
app.include_router(reference_router)
app.include_router(retention_router)
app.include_router(monitoring_router)
