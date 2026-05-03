# MCP Server #2 — Project & Prompt Library Prompts

A structured set of prompts to incrementally build an MCP server that
maintains a personal library of **projects** and **reusable chat prompts**,
queryable from Claude Desktop.

## Decisions to make first

Fill these in before using the prompts below:

- **Storage backend**: SQLite (queryable, single file) or markdown files
  (one per item, IDE-editable, git-friendly)
- **Search**: simple `LIKE`-based, or full-text via SQLite FTS5
- **Storage location**: project-local (`./library.db`), or
  `~/.config/prompt-library/library.db` (cross-machine via dotfiles)
- **Project schema**: minimum `{name, description, status, tags, links}`;
  add `priority`, `deadline`, or `owner`?
- **Prompt schema**: minimum `{title, body, tags, category, notes}`; do you
  want revision history or last-used timestamps?
- **Client**: Claude Desktop only, or also reachable from the Anthropic SDK?

---

## Prompt 1 — Architecture & design

```
I want to build an MCP (Model Context Protocol) server that maintains a
personal library of two kinds of items: projects and chat prompts. It
runs locally on macOS and is invoked from Claude Desktop.

Goals:
- Add, update, list, search, archive, and delete projects and prompts.
- Filter by tags, category, or status.
- Full-text search across titles, descriptions, and bodies.
- Persist to local storage that survives between sessions.
- One source of truth per item (no duplication between cache and store).

Please propose:
1. Storage backend — recommend SQLite or markdown files. Justify the
   choice with the tradeoffs (query speed, human editability, portability,
   conflict-resolution if I sync via Dropbox/iCloud) and propose the schema.
2. The MCP server's directory structure and module layout.
3. The exact list of MCP tools to expose (name, inputs, outputs, purpose).
4. The data flow — how a tool call reads/writes storage and returns
   results to the MCP client.
5. Dependencies and a minimal pyproject.toml.

Do not write code yet. I want a design doc first.
```

---

## Prompt 2 — MCP server skeleton

```
Using the design we agreed on, scaffold the MCP server in Python using
the `mcp` SDK (https://github.com/modelcontextprotocol/python-sdk).

Requirements:
- stdio transport (for Claude Desktop integration).
- Project layout matches the design doc.
- `server.py` initializes the storage backend on startup, runs any
  needed migrations, and registers every tool as a stub.
- Include a `claude_desktop_config.example.json` snippet with absolute
  paths and a placeholder env block.
- Include a Makefile with install / test / smoke / run / register-help /
  clean targets.
- Include a README with setup steps (venv, install, register, run).

Stubs should return placeholder data — no real CRUD logic yet.
```

---

## Prompt 3 — Projects CRUD

```
Implement the project tools:

1. add_project(name, description=None, status="active", tags=[], links={})
2. update_project(id, **fields)
3. list_projects(status=None, tags=None, limit=50)
4. get_project(id)
5. archive_project(id)
6. delete_project(id)

Constraints:
- Writes are atomic (single transaction per call).
- created_at and updated_at are managed automatically; never accept
  them as inputs.
- Tags are normalized (lowercased, trimmed, deduplicated).
- Status is constrained to {active, paused, archived, done}; reject other
  values with a clear error.
- All tools return a structured dict; on failure, return
  {"error": "...", "id": ...} rather than raising.
- name uniqueness is enforced — duplicate adds return an error.

Include unit tests for every tool using a temporary database (tmp_path
or in-memory). Cover: happy path, partial update, tag normalization,
status validation, not-found errors, and uniqueness violation.
```

---

## Prompt 4 — Prompts CRUD + search

```
Implement the prompt tools, mirroring the project tools' patterns:

1. add_prompt(title, body, tags=[], category=None, notes=None)
2. update_prompt(id, **fields)
3. list_prompts(category=None, tags=None, limit=50)
4. get_prompt(id)
5. delete_prompt(id)
6. search_prompts(query, limit=20) — full-text-ranked search across
   title, body, tags, and notes. Use SQLite FTS5 if storage is SQLite;
   otherwise a scored substring match.

Constraints:
- title is unique within the library.
- body is required and non-empty; trim trailing whitespace on save.
- tags normalized as in projects.
- search returns items ordered by relevance with snippets where the
  query matched.

Show me unit tests covering: insert + retrieve, partial update, tag
filtering, category filtering, search ranking on a known corpus, and
the not-found / empty-query / empty-corpus error paths.
```

---

## Prompt 5 — Tag summaries, export, and import

```
Add three helper tools:

1. tag_summary() — returns counts per tag across both projects and
   prompts, plus an "untagged" bucket. Highlights duplicates that differ
   only by case or punctuation so I can clean them up.

2. export_library(kind, format, dest=None) — exports projects, prompts,
   or both to markdown or JSON. Markdown export writes one file per item
   with YAML frontmatter into ./exports/{projects,prompts}/. JSON export
   writes a single file. dest overrides the default output directory.

3. import_library(path) — reads a previously exported markdown or JSON
   tree and merges it into the current library. Conflicting names cause
   an error unless an explicit overwrite flag is set.

Include a smoke test that round-trips a sample library: seed → export →
wipe → import → assert state matches.
```

---

## Prompt 6 — Polish, backup, and deploy

```
Final pass:

1. Add structured logging to stderr (stdout is reserved for MCP). Each
   tool invocation should log name, args, duration_ms, and success/failure.
2. Add a backup tool: backup_library() copies the storage file to
   ./backups/library_YYYY-MM-DD-HHMM.db (or .tar.gz of the markdown
   tree, depending on backend). Returns the absolute path.
3. Document env vars (LIBRARY_PATH, LOG_LEVEL) in the README.
4. Provide the exact Claude Desktop config block with absolute paths.
5. Provide five sample Claude Desktop prompts that exercise the
   server end-to-end:
   - Add a project ("Add a project called 'trading-bot' with tags python, mcp")
   - Find a prompt by topic ("Find my prompt for code review")
   - List by status ("Show all my paused projects")
   - Search across both ("What do I have related to MCP servers?")
   - Run a backup ("Back up my library and tell me the file path")
```

---

## How to use these prompts

Run the prompts one at a time in a fresh session. Paste the previous prompt's
output as context into the next so each step builds on the last. Resolve the
**Decisions to make first** items before Prompt 1 so the design doc has firm
constraints to plan against.
