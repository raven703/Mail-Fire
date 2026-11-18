from app.api import app
from app.ml_api import router

app.include_router(router)
