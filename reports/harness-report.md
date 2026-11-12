# Agent Harness Capability Report

- **Observation date:** 2026-11-12T15:37:38Z
- **Snapshot ID:** `2026-11-12T15-37-38Z`
- **Python version:** 3.11.18
- **Platform:** macOS-26.7.2-x86_64-i386-64bit
- **Skill version:** 0.1.0
- **Probe suite version:** 0.1.0
- **Fingerprint:** `sha256:a679ac5af638e5563f26ec194f6e09569e8c8696e2156b95660d0eee1aa817a2`

## Capability summary

| Metric | Count |
| --- | ---: |
| Python libraries | 77 |
| Uncataloged libraries | 48 |
| Available capabilities | 121 |
| Visible tools / skills / MCP | 41 |
| Restricted | 0 |
| Unknown / unverified | 3 |

## Runtime and environment capabilities

| Capability | Status | Value |
| --- | --- | --- |
| `python.runtime` | available | 3.11.18 |
| `runtime.filesystem:temp-dir` | available | True |
| `runtime.filesystem:write` | unverified |  |
| `runtime.network:https` | unverified |  |
| `runtime.os` | available | Darwin |
| `runtime.subprocess:exec` | unverified |  |
| `skill:{'name': 'agent-harness-explorer'}` | available |  |
| `skill:{'name': 'improve-codebase-architecture'}` | available |  |
| `tool:{'name': 'analyze_code_complexity', 'description': '[MCP:local_dev] Analiza la complejidad de un archivo Python (número de líneas, funciones y clases).', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'bash', 'description': 'Ejecuta un comando de shell (bash) en el sistema. Úsalo para correr tests, instalar dependencias o explorar el sistema.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'create_directory', 'description': '[MCP:filesystem] Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently. Perfect for setting up directory structures for projects or ensuring required paths exist. Only works within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'delegate_to_reviewer', 'description': 'Delega una tarea de revisión de código.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'directory_tree', 'description': "[MCP:filesystem] Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories. Files have no children array, while directories always have a children array (which may be empty). The output is formatted with 2-space indentation for readability. Only works within allowed directories.", 'origin': 'Local'}` | available |  |
| `tool:{'name': 'echo_message', 'description': '[MCP:local_dev] Hace eco de un mensaje. Útil para probar la conexión.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'edit_file', 'description': '[MCP:filesystem] Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made. Only works within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'export_observations', 'description': 'Exporta el inventario de tools, skills y MCP servers del agente a un archivo JSON.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'fetch', 'description': '[MCP:fetch] Fetches a URL from the internet and optionally extracts its contents as markdown.\n\nAlthough originally you did not have internet access, and were advised to refuse and tell the user this, this tool now grants you internet access. Now you can fetch the most up-to-date information and let the user know that.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'get_file_info', 'description': '[MCP:filesystem] Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, last modified time, permissions, and type. This tool is perfect for understanding file characteristics without reading the actual content. Only works within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'get_system_info', 'description': '[MCP:local_dev] Devuelve información sobre el sistema operativo actual (OS, Python, CPU).', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_add', 'description': '[MCP:git] Adds file contents to the staging area', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_branch', 'description': '[MCP:git] List Git branches', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_checkout', 'description': '[MCP:git] Switches branches', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_commit', 'description': '[MCP:git] Records changes to the repository', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_create_branch', 'description': '[MCP:git] Creates a new branch from an optional base branch or commit', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_diff', 'description': '[MCP:git] Shows differences between branches or commits, or across a revision range (main..feature, main...feature)', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_diff_staged', 'description': '[MCP:git] Shows changes that are staged for commit', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_diff_unstaged', 'description': '[MCP:git] Shows changes in the working directory that are not yet staged', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_log', 'description': '[MCP:git] Shows the commit logs', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_merge', 'description': '[MCP:git] Merges a branch into the current branch. Fast-forward only unless fast_forward_only is false; refuses a dirty working tree, and aborts a merge that conflicts, leaving the repository unchanged', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_remote', 'description': "[MCP:git] Lists the repository's remotes with their fetch and push URLs, like `git remote -v`. Credentials embedded in a URL are shown as <redacted>", 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_reset', 'description': '[MCP:git] Unstages all staged changes', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_show', 'description': '[MCP:git] Shows the contents of a commit, or of a file or directory given as <revision>:<path>', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'git_status', 'description': '[MCP:git] Shows the working tree status', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'list_allowed_directories', 'description': '[MCP:filesystem] Returns the list of directories that this server is allowed to access. Subdirectories within these allowed directories are also accessible. Use this to understand which directories and their nested paths are available before trying to access files.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'list_directory', 'description': '[MCP:filesystem] Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is essential for understanding directory structure and finding specific files within a directory. Only works within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'list_directory_with_sizes', 'description': '[MCP:filesystem] Get a detailed listing of all files and directories in a specified path, including sizes. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is useful for understanding directory structure and finding specific files within a directory. Only works within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'load_skill', 'description': "Carga las instrucciones de una 'skill' (habilidad) específica. Úsalo cuando necesites un manual de instrucciones detallado.", 'origin': 'Local'}` | available |  |
| `tool:{'name': 'memory_recall', 'description': 'Search long-term memory.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'memory_save', 'description': 'Save a fact or preference in long-term memory.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'move_file', 'description': '[MCP:filesystem] Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail. Works across different directories and can be used for simple renaming within the same directory. Both source and destination must be within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'read_file', 'description': '[MCP:filesystem] Read the complete contents of a file as text. DEPRECATED: Use read_text_file instead.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'read_media_file', 'description': '[MCP:filesystem] Read a file and return it as a base64-encoded content block with its MIME type. Image and audio files are returned as image/audio content; any other file type is returned as an embedded resource. Only works within allowed directories.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'read_multiple_files', 'description': "[MCP:filesystem] Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation. Only works within allowed directories.", 'origin': 'Local'}` | available |  |
| `tool:{'name': 'read_text_file', 'description': "[MCP:filesystem] Read the complete contents of a file from the file system as text. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Use the 'head' parameter to read only the first N lines of a file, or the 'tail' parameter to read only the last N lines of a file. Operates on the file as text regardless of extension. Only works within allowed directories.", 'origin': 'Local'}` | available |  |
| `tool:{'name': 'run_tests', 'description': '[MCP:local_dev] Ejecuta la suite de tests del proyecto (pytest) y devuelve el resultado o los errores.', 'origin': 'Local'}` | available |  |
| `tool:{'name': 'search_files', 'description': "[MCP:filesystem] Recursively search for files and directories matching a pattern. The patterns should be glob-style patterns that match paths relative to the working directory. Use pattern like '*.ext' to match files in current directory, and '**/*.ext' to match files in all subdirectories. Returns full paths to all matching items. Great for finding files when you don't know their exact location. Only searches within allowed directories.", 'origin': 'Local'}` | available |  |
| `tool:{'name': 'write_file', 'description': '[MCP:filesystem] Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories.', 'origin': 'Local'}` | available |  |

> For the full, category-grouped Python library table, generate the library inventory with `generate_library_inventory.py`.
