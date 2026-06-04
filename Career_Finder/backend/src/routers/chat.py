"""POST /chat — general AI conversation."""

import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google import genai
from dotenv import load_dotenv

from ai.models import ChatRequest, ChatResponse

load_dotenv()
router = APIRouter()

SYSTEM = (
    "You are a helpful career advisor specialising in tech roles. "
    "Be concise, practical, and encouraging."
)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.message or not request.message.strip():
        return JSONResponse(status_code=400, content={"error": "Message cannot be empty."})

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return JSONResponse(status_code=500, content={"error": "GOOGLE_API_KEY not set."})

    contents = (
        f"{SYSTEM}\n\nResume context:\n{request.pdf_text[:3000]}\n\nUser: {request.message}"
        if request.pdf_text
        else f"{SYSTEM}\n\nUser: {request.message}"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash", contents=contents
        )
        return ChatResponse(reply=response.text.strip())

    except Exception as e:
        err = str(e)
        if "429" in err and "PerDay" in err:
            return JSONResponse(status_code=429, content={"error": "Daily API quota exceeded."})
        return JSONResponse(status_code=500, content={"error": f"Chat failed: {e}"})
