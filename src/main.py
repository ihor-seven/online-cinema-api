from fastapi import FastAPI

from src.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.get("/health", tags=["Health"], summary="Check that the API is running")
def health():
    return {"status": "ok"}