from fastapi import FastAPI

app = FastAPI(
    title="GenWorx Auth Service",
    version="0.1.0",
    description="Authentication, session and user-management API.",
)


@app.get("/health", summary="Auth service health", description="Returns service health.")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "auth"}
