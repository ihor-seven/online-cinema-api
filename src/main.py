from fastapi import FastAPI

from src.config import settings
from src.routes.accounts import router as accounts_router
from src.routes.auth import router as auth_router
from src.routes.admin import router as admin_router
from src.routes.passwords import router as passwords_router
from src.routes.movies import router as movies_router
from src.routes.interactions import router as interactions_router
from src.routes.cart import router as cart_router
from src.routes.orders import router as orders_router


app = FastAPI(title=settings.app_name, debug=settings.debug)


app.include_router(accounts_router)
app.include_router(auth_router)
app.include_router(passwords_router)
app.include_router(admin_router)
app.include_router(movies_router)
app.include_router(interactions_router)
app.include_router(cart_router)
app.include_router(orders_router)


@app.get("/health", tags=["Health"], summary="Check that the API is running")
def health():
    return {"status": "ok"}
