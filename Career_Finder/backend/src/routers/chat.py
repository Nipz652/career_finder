"""
/chat router.
General AI conversation with optional resume context.
"""

import os
import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google import genai
from dotenv import load_dotenv

from ai.models import ChatRequest, ChatResponse
from ai.extractor import DailyQuotaExceededError, InvalidRequestError

load_dotenv()

router = APIRouter()

CHAT_SYSTEM_CONTEXT = """You are a helpful career advisor specialising in tech roles.
You help candidates understand the job market, improve their skills, and plan their careers.
Be concise, practical, and encouraging."""


def _get_client() -> genai.Client:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    General career advisor chat.

    If pdf_text is provided, it is included as context so the AI
    can answer questions about the specific resume.

    Request body:
        message: User's chat message
        pdf_text: Optional resume text for context

    Returns:
        ChatResponse with reply string.
    """
    if not request.message or not request.message.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Message cannot be empty."},
        )

    # Build contents
    if request.pdf_text:
        contents = (
            f"{CHAT_SYSTEM_CONTEXT}\n\n"
            f"The user has shared their resume:\n\n"
            f"{request.pdf_text[:3000]}\n\n"   # cap at 3000 chars
            f"User: {request.message}"
        )
    else:
        contents = f"{CHAT_SYSTEM_CONTEXT}\n\nUser: {request.message}"

    try:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
        )
        return ChatResponse(reply=response.text.strip())

    except Exception as e:
        error_str = str(e)

        if "429" in error_str and "PerDay" in error_str:
            return JSONResponse(
                status_code=429,
                content={
                    "error": (
                        "Daily API quota exceeded. "
                        "Please try again tomorrow."
                    )
                },
            )

        if "400" in error_str and "INVALID_ARGUMENT" in error_str:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid request to AI model."},
            )

        return JSONResponse(
            status_code=500,
            content={"error": f"Chat failed: {str(e)}"},
        )