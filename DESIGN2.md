# MCP Server #2 — Project & Prompt Library (Design Doc)

**Status:** Draft — output of Prompt 1 in [MCP_SERVER_PROMPTS2.md](MCP_SERVER_PROMPTS2.md)
**Scope:** Local MCP server (stdio) for Claude Desktop and the Anthropic SDK. Maintains a personal library of projects and reusable chat prompts in a single SQLite file.

---

## 1. Storage backend — SQLite + FTS5

**Recommendation:** SQLite, per the user's decision.

Reasoning vs the alternative (markdown files):

| Concern | SQLite | Markdown files |
|---|---|---|
| Query speed for tag/status filters | O(log N) with an index | Linear scan or external index |
| Full-text search | Native FTS5, ranked, with snippets | grep — no ranking |
| Conflict resolution if synced | Single file, last-write-wins; rarely conflicts | Per-file diffs, but YAML frontmatter merges are messy |
| Human editability | Requires SQL or this server | Open in any editor |
| Portability | One file (~MB scale) | Tree of files |
| Atomic transactions | Native | Hard to do safely |

Wins the design because the user wants ranked full-text search and tag-filtered queries — both are awkward to do over a markdown tree. Human editability is preserved via the `export_library` and `import_library` tools (Prompt 5), which round-trip the SQLite store to a markdown tree on demand.

### Schema

```sql
CREATE TABLE projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active', 'paused', 'archived', 'done')),
    links       TEXT,                      -- JSON object {label: url}
    created_at  TEXT NOT NULL,             -- ISO 8601 UTC
    updated_at  TEXT NOT NULL              -- ISO 8601 UTC
);

CREATE TABLE prompts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT UNIQUE NOT NULL,
    body        TEXT NOT NULL,
    category    TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL              -- normalized: lowercase, trimmed
);

CREATE TABLE project_tags (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    tag_id     INTEGER NOT NULL REFERENCES tags(id)     ON DELETE CASCADE,
    PRIMARY KEY (project_id, tag_id)
);

CREATE TABLE prompt_tags (
    prompt_id INTEGER NOT NULL REFERENCES prompts(id) ON DELETE CASCADE,
    tag_id    INTEGER NOT NULL REFERENCES tags(id)    ON DELETE CASCADE,
    PRIMARY KEY (prompt_id, tag_id)
);

-- FTS5 virtual table for ranked prompt search.
CREATE VIRTUAL TABLE prompts_fts USING fts5(
    title, body, category, notes,
    content='prompts',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers keep prompts_fts in sync with prompts.
CREATE TRIGGER prompts_ai AFTER INSERT ON prompts BEGIN
    INSERT INTO prompts_fts(rowid, title, body, category, notes)
    VALUES (new.id, new.title, new.body, new.category, new.notes);
END;
CREATE TRIGGER prompts_ad AFTER DELETE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title, body, category, notes)
    VALUES('delete', old.id, old.title, old.body, old.category, old.notes);
END;
CREATE TRIGGER prompts_au AFTER UPDATE ON prompts BEGIN
    INSERT INTO prompts_fts(prompts_fts, rowid, title, body, category, notes)
    VALUES('delete', old.id, old.title, old.body, old.category, old.notes);
    INSERT INTO prompts_fts(rowid, title, body, category, notes)
    VALUES (new.id, new.title, new.body, new.category, new.notes);
END;

-- Schema version tracking, for future migrations.
CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version(version) VALUES (1);
```

**Storage path:** `~/.config/prompt-library/library.db` (override via `LIBRARY_PATH` env var). Directory is created on first run.

---

## 2. Directory structure

```
prompt-library/
├── prompt_library/
│   ├── __init__.py
│   ├── server.py                 # MCP entry point (stdio)
│   ├── config.py                 # env vars, paths
│   ├── logging_setup.py          # stderr logging + log_tool decorator
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── library.py            # Library class — SQLite-backed CRUD
│   │   ├── schema.sql            # DDL above
│   │   ├── migrations.py         # version-tracked schema upgrades
│   │   └── models.py             # TypedDicts for return shapes
│   └── tools/
│       ├── __init__.py
│       ├── project_tools.py      # MCP wrappers for project CRUD
│       ├── prompt_tools.py       # MCP wrappers for prompt CRUD + search
│       └── library_tools.py      # tag_summary, export, import, backup
├── tests/
│   ├── conftest.py               # tmp_path fixture for isolated DBs
│   ├── test_projects.py
│   ├── test_prompts.py
│   ├── test_search.py
│   └── test_export_import.py
├── exports/                      # gitignored, runtime output
├── backups/                      # gitignored, runtime output
├── .env.example
├── pyproject.toml
├── Makefile
├── claude_desktop_config.example.json
└── README.md
```

**Layering rule:** `tools/` → `storage/`. Tools are thin MCP adapters; never write SQL directly. The `Library` class is the only thing that touches SQLite.

**Dual-client design:** Because the user wants this reachable from the Anthropic SDK as well as Claude Desktop, the `Library` class is the public Python API:

```python
from prompt_library.storage.library import Library
lib = Library()  # reads LIBRARY_PATH env var
project = lib.add_project(name="trading-bot", tags=["python", "mcp"])
```

The MCP server is a thin facade over `Library`. Both clients exercise the same code path.

---

## 3. MCP tools to expose

### Projects (6)

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `add_project` | `name`, `description?`, `status='active'`, `tags=[]`, `links={}` | New project dict | Create. |
| `update_project` | `id`, `**fields` | Updated project dict | Partial update. |
| `list_projects` | `status?`, `tags?`, `limit=50` | List of project dicts | Filter + page. |
| `get_project` | `id` (or `name`) | Project dict | Read one. |
| `archive_project` | `id` | Updated project dict | Sets status='archived'. |
| `delete_project` | `id` | `{deleted: true, id}` | Hard delete (cascades tags). |

### Prompts (6)

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `add_prompt` | `title`, `body`, `tags=[]`, `category?`, `notes?` | New prompt dict | Create. |
| `update_prompt` | `id`, `**fields` | Updated prompt dict | Partial update. |
| `list_prompts` | `category?`, `tags?`, `limit=50` | List of prompt dicts | Filter + page. |
| `get_prompt` | `id` (or `title`) | Prompt dict | Read one. |
| `delete_prompt` | `id` | `{deleted: true, id}` | Hard delete. |
| `search_prompts` | `query`, `limit=20` | List of `{prompt, snippet, rank}` | FTS5-ranked search across title/body/category/notes. |

### Library helpers (4)

| Tool | Inputs | Output | Purpose |
|---|---|---|---|
| `tag_summary` | — | `{by_tag: {tag: {projects, prompts}}, untagged: ..., near_duplicates: [...]}` | Audit tags; flag near-duplicates. |
| `export_library` | `kind` (projects/prompts/all), `format` (markdown/json), `dest?` | `{paths: [...]}` | Round-trip to markdown tree or single JSON file. |
| `import_library` | `path`, `overwrite=false` | `{imported: N, skipped: M}` | Merge an export back into the DB. |
| `backup_library` | — | `{path}` | Copies the DB file to `./backups/library_YYYY-MM-DD-HHMM.db`. |

**Total: 16 MCP tools.**

---

## 4. Data flow

```
Claude Desktop / SDK
        │
        │  MCP stdio (JSON-RPC)
        ▼
prompt_library/server.py              ← FastMCP, registers all 16 tools
        │
        │  log_tool decorator: name, args, duration_ms, status
        ▼
prompt_library/tools/{project,prompt,library}_tools.py
        │
        │  validates inputs, normalizes tags
        ▼
prompt_library/storage/library.py     ← Library class, single SQLite connection
        │
        │  parameterized SQL, single transaction per call
        ▼
~/.config/prompt-library/library.db   ← single file, FTS5 enabled
```

Every tool returns a `dict`. On failure, tools return `{"error": "...", ...}` rather than raising — same pattern as the trading-bot server. The `Library` class itself raises typed exceptions (`NotFoundError`, `DuplicateError`, `ValidationError`) which the wrappers translate into error dicts.

---

## 5. Dependencies

```toml
[project]
name = "prompt-library-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
    "ruff>=0.5.0",
]

[project.scripts]
prompt-library-mcp = "prompt_library.server:main"

[tool.setuptools.packages.find]
include = ["prompt_library*"]
```

**Stdlib-only for storage and search:** `sqlite3`, `json`, `pathlib`, `datetime`. FTS5 ships in modern SQLite (verify with `sqlite3 --version` ≥ 3.9).

**Markdown export uses JSON frontmatter** — avoids a YAML dependency. If prettier YAML frontmatter is preferred later, add `pyyaml` to deps.

**Required environment variables:**
- `LIBRARY_PATH` (optional) — full path to the SQLite file. Default: `~/.config/prompt-library/library.db`.
- `LOG_LEVEL` (optional) — `INFO`, `DEBUG`, etc. Default: `INFO`.

---

## Open questions before Prompt 2

1. **Tag normalization rules:** lowercase + trim is obvious. Should we also strip punctuation (e.g., treat `mcp.` and `mcp` as the same)? My recommendation: trim and lowercase only; `tag_summary` flags near-duplicates so the user can clean up manually.
2. **Project lookup by name:** `get_project` accepts id or name — do we want case-insensitive name match? My recommendation: yes, since name is unique anyway.
3. **Markdown export filenames:** by `id`, by slugified `name`/`title`, or both (`{id}_{slug}.md`)? My recommendation: `{slug}.md`, with id stored in the frontmatter.
4. **Confirmation on destructive ops:** `delete_*` and `import_library --overwrite` — require an explicit `confirm: true` flag? My recommendation: yes for `delete_project`/`delete_prompt`; not needed for archive.
5. **First-run UX:** create the DB file silently on first call, or require an explicit `init` step? My recommendation: silent — just create the parent directory and run migrations.

Resolve these before scaffolding in Prompt 2.
