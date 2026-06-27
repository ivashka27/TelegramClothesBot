from __future__ import annotations

from database.models import WardrobeItem


def format_items_expandable_list(items: list[WardrobeItem], header: str, footer: str) -> str:
    if not items:
        return "Гардероб пуст."
    lines = "\n".join(f"• {item.name}" for item in items)
    return f"{header}\n<blockquote expandable>{lines}</blockquote>\n\n{footer}"


def format_wardrobe_list_markdown(items: list[WardrobeItem]) -> str:
    if not items:
        return "👗 Ваш гардероб пока пуст."
    lines = ["👗 **Ваш гардероб:**\n"]
    for item in items:
        cat = f" ({item.category})" if item.category else ""
        desc = f" — {item.description}" if item.description else ""
        lines.append(f"• {item.name}{cat}{desc}")
    return "\n".join(lines)
