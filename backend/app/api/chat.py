"""问答 API — SSE 流式输出

对齐 API.md §6：
- POST /api/chat — 问答 SSE 流式输出
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.schemas.chat import ChatRequest
from app.services.chat_service import chat

router = APIRouter(prefix="/api", tags=["问答"])


@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """问答接口 — SSE 流式返回答案。

    对齐 API.md §6：
    - 连接建立前的参数校验错误直接返回 HTTP JSON
    - SSE 连接后的检索/LLM 错误通过 event: error 发送
    - 事件序列：meta → thinking(可选) → message → sources → finish
    """
    return await chat(
        db=db,
        user_id=current_user["user_id"],
        role=current_user["role"],
        conversation_id=req.conversation_id,
        kb_id=req.kb_id,
        question=req.question,
        deep_thinking=req.deep_thinking,
    )
