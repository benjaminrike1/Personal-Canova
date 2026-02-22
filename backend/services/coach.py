"""Claude coaching engine — context builder + conversation handler.

Handles:
- Building dynamic system prompts via ContextBuilder
- Sending messages to Claude API
- Parsing structured responses (notebook entries, plan adjustments)
- Storing conversation history
"""

import json
import logging
import re

import anthropic

from backend.core.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS
from backend.core.database import get_db
from backend.services.context import ContextBuilder

log = logging.getLogger(__name__)

# Regex patterns for structured coach outputs
NOTEBOOK_PATTERN = re.compile(r"```notebook\s*\n(.*?)\n```", re.DOTALL)
PLAN_ADJ_PATTERN = re.compile(r"```plan_adjustment\s*\n(.*?)\n```", re.DOTALL)


class CoachEngine:
    """Manages Claude API interactions with full dynamic context injection."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.context_builder = ContextBuilder()

    async def send_message(
        self,
        conversation_id: int,
        user_message: str,
    ) -> dict:
        """Send a user message and get the coach's response.

        Returns:
            {
                "response": str,           # The coach's text reply
                "notebook_entries": [...],  # Any new notebook observations
                "plan_adjustments": [...],  # Any plan changes
            }
        """
        # 1. Store the user message
        with get_db() as db:
            db.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
                (conversation_id, user_message),
            )

        # 2. Build system prompt with full context
        system_prompt = self.context_builder.build_system_prompt(conversation_id)

        # 3. Get conversation history
        messages = self.context_builder.get_conversation_messages(conversation_id)

        # 4. Call Claude API
        try:
            api_response = self.client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=ANTHROPIC_MAX_TOKENS,
                system=system_prompt,
                messages=messages,
            )
            response_text = api_response.content[0].text
        except anthropic.APIError as e:
            log.error(f"Claude API error: {e}")
            response_text = "I'm having trouble connecting right now. Please try again in a moment."

        # 5. Parse structured outputs (notebook entries, plan adjustments)
        notebook_entries = self._extract_notebook_entries(response_text)
        plan_adjustments = self._extract_plan_adjustments(response_text)

        # 6. Clean response text (remove structured blocks for display)
        clean_response = NOTEBOOK_PATTERN.sub("", response_text)
        clean_response = PLAN_ADJ_PATTERN.sub("", clean_response).strip()

        # 7. Store the assistant response
        with get_db() as db:
            db.execute(
                "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
                (conversation_id, clean_response),
            )
            # Update conversation timestamp
            db.execute(
                "UPDATE conversations SET updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                (conversation_id,),
            )

        # 8. Process notebook entries
        self._save_notebook_entries(notebook_entries, conversation_id)

        # 9. Process plan adjustments
        self._apply_plan_adjustments(plan_adjustments)

        return {
            "response": clean_response,
            "notebook_entries": notebook_entries,
            "plan_adjustments": plan_adjustments,
        }

    def create_conversation(self, title: str | None = None, conversation_type: str = "general") -> int:
        """Create a new conversation and return its ID."""
        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO conversations (title, conversation_type) VALUES (?, ?)",
                (title or "New conversation", conversation_type),
            )
            return cursor.lastrowid

    def _extract_notebook_entries(self, text: str) -> list[dict]:
        """Extract notebook entries from ```notebook blocks."""
        entries = []
        for match in NOTEBOOK_PATTERN.finditer(text):
            try:
                entry = json.loads(match.group(1))
                if "category" in entry and "content" in entry:
                    entries.append(entry)
            except json.JSONDecodeError:
                log.warning(f"Failed to parse notebook entry: {match.group(1)}")
        return entries

    def _extract_plan_adjustments(self, text: str) -> list[dict]:
        """Extract plan adjustments from ```plan_adjustment blocks."""
        adjustments = []
        for match in PLAN_ADJ_PATTERN.finditer(text):
            try:
                adj = json.loads(match.group(1))
                if "entry_id" in adj:
                    adjustments.append(adj)
            except json.JSONDecodeError:
                log.warning(f"Failed to parse plan adjustment: {match.group(1)}")
        return adjustments

    def _save_notebook_entries(self, entries: list[dict], conversation_id: int):
        """Save extracted notebook entries to the database."""
        if not entries:
            return
        with get_db() as db:
            for entry in entries:
                db.execute(
                    """INSERT INTO coach_notebook
                       (category, content, confidence, source_type, source_conversation_id)
                       VALUES (?, ?, ?, 'conversation', ?)""",
                    (
                        entry.get("category", "observation"),
                        entry["content"],
                        entry.get("confidence", "medium"),
                        conversation_id,
                    ),
                )
        log.info(f"Saved {len(entries)} notebook entries from conversation {conversation_id}")

    def _apply_plan_adjustments(self, adjustments: list[dict]):
        """Apply plan adjustments from the coach's response."""
        if not adjustments:
            return
        with get_db() as db:
            for adj in adjustments:
                entry_id = adj.get("entry_id")
                changes = adj.get("changes", {})
                reason = adj.get("reason", "Coach adjustment")

                if not entry_id or not changes:
                    continue

                # Get current state for version history
                current = db.execute(
                    "SELECT * FROM training_plan WHERE id = ?", (entry_id,)
                ).fetchone()
                if not current:
                    log.warning(f"Plan entry {entry_id} not found for adjustment")
                    continue

                current_dict = dict(current)
                new_version = current_dict.get("version", 1) + 1

                # Save version
                db.execute(
                    """INSERT INTO training_plan_versions
                       (plan_entry_id, version, previous_data, change_reason, changed_by)
                       VALUES (?, ?, ?, ?, 'coach')""",
                    (entry_id, current_dict["version"], json.dumps(current_dict), reason),
                )

                # Apply changes
                allowed_fields = {
                    "session_type", "target_duration_s", "target_intensity",
                    "key_objective", "is_key_session", "is_rest_day",
                    "deviation_notes",
                }
                update_parts = []
                update_vals = []
                for field, value in changes.items():
                    if field in allowed_fields:
                        update_parts.append(f"{field} = ?")
                        update_vals.append(value)

                if update_parts:
                    update_parts.append("version = ?")
                    update_vals.append(new_version)
                    update_parts.append("updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')")
                    update_vals.append(entry_id)
                    db.execute(
                        f"UPDATE training_plan SET {', '.join(update_parts)} WHERE id = ?",
                        update_vals,
                    )

        log.info(f"Applied {len(adjustments)} plan adjustments")
