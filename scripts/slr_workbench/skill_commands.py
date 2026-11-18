"""Workspace setup and the single skill's optional command entry points."""

import importlib.util
import re
import tempfile
from importlib.resources import files
from pathlib import Path

import yaml

from . import __version__


def new_review(project, reviewer):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", reviewer):
        raise ValueError("Choose a reviewer ID with letters, digits, dots, hyphens or underscores.")
    target = project.resolve()
    if target.exists():
        raise FileExistsError("Choose a new review directory.")
    target.parent.mkdir(parents=True, exist_ok=True)
    resources = files("slr_workbench").joinpath("templates")
    with tempfile.TemporaryDirectory(prefix=".new-slr-", dir=target.parent) as temporary:
        staged = Path(temporary) / "review"
        staged.mkdir()
        protocol = yaml.safe_load(resources.joinpath("protocol.yaml").read_text(encoding="utf-8"))
        protocol["reviewers"]["identities"] = [reviewer]
        (staged / "protocol.yaml").write_text(
            yaml.safe_dump(protocol, sort_keys=False), encoding="utf-8"
        )
        for name in ("workflow.yaml", "conversion.yaml", "rag.yaml"):
            (staged / name).write_bytes(resources.joinpath(name).read_bytes())
        if target.exists():
            raise FileExistsError("Choose a new review directory.")
        staged.rename(target)
    return {
        "workspace": str(target),
        "reviewer": reviewer,
        "next": "Replace the synthetic protocol, initialize, and hand approval to the reviewer.",
    }


def dispatch(command, project, args):
    if command == "new-review":
        return new_review(project, args["reviewer"])
    if command == "doctor":
        return {
            "version": __version__,
            "python_modules": {
                name: importlib.util.find_spec(name) is not None
                for name in ("pypdf", "pymupdf", "fastembed", "docling", "chromadb")
            },
            "workspace": str(project.resolve()),
            "has_protocol": (project / "protocol.yaml").is_file(),
            "has_workflow": (project / "workflow.yaml").is_file(),
            "note": "Network, provider credentials, Ollama and image tools require separate checks.",
        }
    if command == "rank-papers":
        from .ranking import rank

        return rank(project, **args)
    if command == "fetch-pdf":
        from .pdf_retrieval import retrieve_pdf

        return retrieve_pdf(**args)
    if command == "snowball":
        from .search.citations import snowball

        return snowball(project, **args)
    if command == "refresh-search":
        from .search.archive import verify_bundle
        from .search.service import search

        previous, _ = verify_bundle(args["manifest"])
        cap = (
            args["max_results"]
            if args["max_results"] is not None
            else previous.get("max_results", 100)
        )
        result = search(
            project,
            previous["provider"],
            previous["query"],
            max_results=cap,
            allow_credentials=args["allow_credentials"],
        )
        return {**result, "refreshed_from_run": previous["run_id"]}
    raise ValueError(f"Unknown skill command: {command}")
