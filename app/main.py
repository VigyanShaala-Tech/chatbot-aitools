from fastapi import FastAPI, Depends
from app.routers import websearch, files
from app.core.config import settings
from app.core.security import get_api_key

app = FastAPI(title="Glific Websearch & File Analysis Bot", dependencies=[Depends(get_api_key)])

app.include_router(websearch.router, tags=["Websearch"])
app.include_router(files.router, tags=["File Analysis"])

@app.get("/health")
async def health():
    return {"status": "ok"}
