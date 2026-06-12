"""octowiz.plan capability — doctrine enrichment for planning tasks."""
from typing import Any, Dict, Optional

from capabilities.doctrine_enrichment import handle_doctrine_enrichment


def _plan_prompt_builder(event: Dict, context: Any) -> str:
    task = event.get("task", "")
    prompt = f"[octowiz.plan] {task}"
    if context:
        prompt += f"\n\nContext:\n{context}"
    return prompt


async def handle_plan(event: Dict, *, source: Optional[Any] = None) -> Dict:
    task = event.get("task", "")
    if not task:
        return {"status": "error", "message": "task is required"}
    result = await handle_doctrine_enrichment(event, "planner", _plan_prompt_builder, source=source)
    return {**result, "task": task}
