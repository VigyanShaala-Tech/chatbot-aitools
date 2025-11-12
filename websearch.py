import os
from typing import Any, Dict
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import uvicorn

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class QueryRequest(BaseModel):
    query: str

@app.post("/search")
async def search(req: QueryRequest) -> Dict[str, Any]:
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty")

    try:
        client = OpenAI()
        resp = client.responses.create(model="gpt-5", tools=[{"type": "web_search"}], input=req.query)

        out = {}
        
        out["model"] = getattr(resp, "model", None)
        out["id"] = getattr(resp, "id", None)
        out["created"] = getattr(resp, "created", None)

        # grab text content from response
        pieces = []
        for item in getattr(resp, "output", []) or []:
            item = item.to_dict() if hasattr(item, "to_dict") else item
            if isinstance(item, dict):
                for c in item.get("content", []):
                    if isinstance(c, dict) and "text" in c:
                        pieces.append(c["text"])
                    elif isinstance(c, str):
                        pieces.append(c)
        
        out["text"] = "\n\n".join(pieces) if pieces else None
        return {"ok": True, "openai_response": out['text']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("websearch:app", host="0.0.0.0", port=8000, reload=False)