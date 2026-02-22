"""Claude coaching engine — context builder + conversation handler."""


class CoachEngine:
    """Manages Claude API interactions with full dynamic context injection."""

    async def build_system_prompt(self) -> str:
        raise NotImplementedError

    async def send_message(self, conversation_id: int, user_message: str) -> str:
        raise NotImplementedError
