from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.rest.routes import auth, health, users

app = FastAPI(
    title="GenWorx AP Auth Service",
    version="0.1.0",
    description="Authentication service for GenWorx AP Assistant",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "genworx-ap-auth",
        "status": "running",
    }
