# Skill: Rich Formatting for TUI

You have the ability to render rich content in the Terminal User Interface (TUI). Instead of plain text, you can return special fenced code blocks that the TUI will parse and render natively.

**When to use this:** Use these blocks whenever you need to present structured data, directory structures, or code. It makes your response much more readable for the user.

## 1. Tables (`table`)

To render a table, use the `table` tag. **You must use standard Markdown table formatting** (including the `| --- |` separator row). The TUI will render it natively.

```table
| Tool Name       | Category | Status |
| :-------------- | :------- | :----- |
| bash            | Local    | Active |
| read_file       | Local    | Active |
| get_system_info | MCP      | Active |
```

## 2. Trees (`tree`)

To render hierarchical data (like a directory structure), use the `tree` tag. Each line will be a node in the tree.

```tree
agent-harness/
  app/
    core/
      harness/
    tui/
  tests/
    core/
    tui/
  .env
  pyproject.toml
```

## 3. JSON to Table (`json`)

If you return a list of JSON objects (where all objects have the same keys), the TUI will automatically convert it into a beautifully formatted table. Use the `json` tag.

```json
[
  { "name": "bash", "origin": "Local", "params": "command" },
  { "name": "get_system_info", "origin": "MCP", "params": "none" },
  { "name": "memory_save", "origin": "Local", "params": "key, value" }
]
```

## 4. Syntax Highlighting

Use standard markdown code blocks with the language identifier for syntax highlighting. The TUI supports Python, Bash, JSON, YAML, and many others.

```python
def hello_harness():
    print("Hello from the Rich TUI!")
```

## Important Rules

- **Do not overuse**: Only use these blocks when they add value. For normal conversation, stick to standard Markdown.
- **Valid Syntax**: Ensure the JSON block is valid JSON, and the table block has a consistent number of columns per row.
