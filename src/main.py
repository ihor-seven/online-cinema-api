from fastapi import FastAPI

from src.config import settings
from src.routes.accounts import router as accounts_router

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(accounts_router)


@app.get("/health", tags=["Health"], summary="Check that the API is running")
def health():
    return {"status": "ok"}