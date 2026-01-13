from fastapi import FastAPI
from app.routers import websearch, files
from app.core.config import settings

app = FastAPI(title="Glific Websearch & File Analysis Bot")

app.include_router(websearch.router, tags=["Websearch"])
app.include_router(files.router, tags=["File Analysis"])

@app.get("/health")
async def health():
    return {"status": "ok"}
