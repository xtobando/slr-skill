# Native skill setup

Install this complete skill folder in one of the runtime's skill directories. Keep the scripts, templates, and references together.

| Runtime | Project directory | Personal directory |
| --- | --- | --- |
| Claude Code | `.claude/skills/systematic-literature-review/` | `~/.claude/skills/systematic-literature-review/` |
| OpenCode | `.opencode/skills/systematic-literature-review/` | `~/.config/opencode/skills/systematic-literature-review/` |

OpenCode also discovers Claude-compatible skill locations. In Claude Code invoke `/systematic-literature-review TOPIC`. In OpenCode ask it to load `systematic-literature-review` and perform the task. For another runtime, place the same complete folder in its documented Agent Skills location.

## Automatic setup with uv (recommended)

Read the absolute path of the loaded SKILL.md. Let SKILL_ROOT be its containing directory. Always use its absolute `scripts/slr.py` path, regardless of the terminal's current directory. Distribute the complete folder, including `scripts/slr.py.lock`; do not copy only SKILL.md.

Check `uv --version`. If available, references abbreviate this command prefix as `{SLR}`:

```sh
uv run --locked --python 3.11 --script "ABSOLUTE_SKILL_ROOT/scripts/slr.py"
```

Replace the placeholder with the actual absolute skill root. The same syntax works in PowerShell and macOS/Linux shells. Then run:

```sh
uv run --locked --python 3.11 --script "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --version
uv run --locked --python 3.11 --script "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --project "WORKSPACE" doctor
```

uv automatically obtains Python 3.11 if needed and installs locked core dependencies into its cached script environment. No activation, MCP server, hardcoded user path, or AGENTS.md modification is needed. Python and package downloads require network access on first use; later runs reuse the cache. Leave uv's cache outside the skill folder and review workspace. Respect runtime installation/network permissions and explain downloads before the first setup.

### If uv is missing

Request authorization for a one-time uv installation; do not silently install a package manager or change shell policy. Offer the official [installation instructions](https://docs.astral.sh/uv/getting-started/installation/). The user can run the appropriate installer in their own terminal:

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS/Linux:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

These commands download and execute the official installer; run only with the user's consent. Refresh the terminal's PATH as instructed by the installer, or invoke the installed uv executable by its absolute path. Recheck `uv --version`. If installation is declined, blocked or unavailable, use the Python fallback below; never override a denied operation.

## Optional capabilities

Keep optional dependencies out of the core installation. For requested FastEmbed ranking, add `--with "fastembed>=0.4,<1"` before `--script`:

```sh
uv run --locked --python 3.11 --with "fastembed>=0.4,<1" --script "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --project "WORKSPACE" rank-papers --query "QUESTION" --output "ABSOLUTE_RANKING_JSON"
```

Add `--manifest "ABSOLUTE_MANIFEST_JSON"` for standalone search bundles. uv provisions the extra libraries on demand; first ranking use also downloads model weights. The optional overlay is not pinned by the core script lockfile: record actual versions/model provenance and do not claim a fully locked ranking environment.

For Ollama use `{SLR}` with `--backend ollama --model MODEL` and an already running local embedding service; FastEmbed is not needed. Optional Docling or Chroma features need their own installed libraries and models. Core dependencies support PDF text extraction and page rendering, not automatic OCR of scanned PDFs. Explain available capabilities before use. Network restrictions can still allow query drafting, saved imports, and local PDF reading when dependencies are already available.

## Python fallback

Use an existing Python 3.11+ environment if the required libraries are available. Otherwise create a dedicated virtual environment outside both the skill folder and a new review target, such as `PARENT/.slr-runtime`. Follow runtime permission requirements; do not install globally or bypass a denied installation.

macOS/Linux, substituting actual absolute paths and a Python 3.11+ interpreter:

```sh
python3 -m venv "PARENT/.slr-runtime"
"PARENT/.slr-runtime/bin/python" -m pip install -r "ABSOLUTE_SKILL_ROOT/scripts/requirements.txt"
"PARENT/.slr-runtime/bin/python" "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --version
"PARENT/.slr-runtime/bin/python" "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --project "WORKSPACE" doctor
```

Windows PowerShell:

```powershell
py -3.11 -m venv "PARENT/.slr-runtime"
& "PARENT/.slr-runtime/Scripts/python.exe" -m pip install -r "ABSOLUTE_SKILL_ROOT/scripts/requirements.txt"
& "PARENT/.slr-runtime/Scripts/python.exe" "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --version
& "PARENT/.slr-runtime/Scripts/python.exe" "ABSOLUTE_SKILL_ROOT/scripts/slr.py" --project "WORKSPACE" doctor
```

In fallback mode, `{SLR}` means that interpreter followed by the absolute script path, quoting both paths and using PowerShell's `&` before a quoted executable. Install `fastembed>=0.4,<1` in that environment only when needed. The requirements fallback uses version ranges, not the uv lockfile's exact pins.

## Credentials and human decisions

Do not configure accounts or store secrets in the skill folder. Have the user run `{SLR} credentials PROVIDER set` in their own terminal when needed. Credentialed or potentially paid searches still require explicit authorization and `--allow-credentials`. Automatic environment setup does not authorize protocol approval or scientific decisions on the human's behalf.

## Create or resume a workspace

For a new formal review use `{SLR} --project NEW_WORKSPACE new-review --reviewer HUMAN_ID`. Replace the synthetic topic and criteria before `init`, then hand the approval command to the reviewer. Keep research data outside the installed skill folder. For an existing review inspect `status`, `workflow`, and the saved protocol. Search-only and standalone PDF reading work without protocol approval.

## Maintaining a distributable release

The PEP 723 dependency block in `scripts/slr.py` is the core dependency declaration. Keep `scripts/requirements.txt` consistent for the Python fallback. After changing dependencies, regenerate and check the adjacent lockfile:

```sh
uv lock --script "ABSOLUTE_SKILL_ROOT/scripts/slr.py"
uv lock --check --script "ABSOLUTE_SKILL_ROOT/scripts/slr.py"
```

Ship `slr.py.lock` with every release and smoke-test `--version` and `doctor` using the locked command. Use a public package index when generating a public release; do not distribute private index URLs or credentials. End users should not regenerate or upgrade the lockfile during routine execution. If it is missing or stale, report the incomplete installation and obtain a complete release or use the documented fallback with its reproducibility limits.
