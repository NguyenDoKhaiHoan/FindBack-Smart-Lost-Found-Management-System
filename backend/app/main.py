from fastapi import FastAPI

from app.modules.identity.routers import router as identity_router

app = FastAPI(title="FindBack API", version="0.1.0")
app.include_router(identity_router)
