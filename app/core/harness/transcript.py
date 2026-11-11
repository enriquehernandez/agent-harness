import json


def render_transcript(messages: list[dict], fmt: str = "markdown") -> str:
    if fmt == "json":
        return json.dumps(messages, indent=2, ensure_ascii=False)
    elif fmt == "markdown":
        lines = []
        for m in messages:
            role = m["role"].capitalize()
            content = m.get("content", "")
            if content:
                lines.append(f"### {role}\n{content}\n")
        return "\n".join(lines)
    else:
        return "\n".join([f"[{m['role']}] {m.get('content', '')}" for m in messages])
