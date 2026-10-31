"""LangGraph conversation state; messages are merged by the native reducer."""

from langgraph.graph import MessagesState


class ConversationState(MessagesState):
    summary: str
