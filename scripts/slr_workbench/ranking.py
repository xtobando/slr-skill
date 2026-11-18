"""Read-only title/abstract ranking. Semantic scores never write eligibility."""

import hashlib
import json
import math
from importlib.metadata import version
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, build_opener

from .search.archive import read_json, save, verify_bundle
from .search.http import NoRedirect


def unit_vector(values):
    try:
        vector = [float(value) for value in values]
        norm = math.hypot(*vector)
        if not norm or not math.isfinite(norm):
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Embedding returned a non-finite, empty or zero vector.") from None
    return [value / norm for value in vector]


def embedding_backend(backend, model, port):
    if backend == "fastembed":
        try:
            from fastembed import TextEmbedding
        except ImportError:
            raise ValueError("Install the 'embeddings' extra or use the Ollama backend.") from None
        engine = TextEmbedding(model_name=model, threads=4)
        return lambda texts, query: list(
            (engine.query_embed if query else engine.passage_embed)(texts, batch_size=8)
        ), {"package_version": version("fastembed")}

    def request(path, payload=None):
        data = json.dumps(payload).encode() if payload is not None else None
        try:
            with build_opener(NoRedirect()).open(
                Request(
                    f"http://127.0.0.1:{port}{path}",
                    data,
                    headers={"Content-Type": "application/json"},
                ),
                timeout=120,
            ) as response:
                return json.load(response)
        except (URLError, OSError, ValueError):
            raise ValueError(
                "Local Ollama embedding request failed. Check the model and context size."
            ) from None

    try:
        models = request("/api/tags")["models"]
        model_names = {model, model + ":latest"} if ":" not in model else {model}
        digest = next(row["digest"] for row in models if row.get("name") in model_names)
    except (KeyError, TypeError, StopIteration):
        raise ValueError("The requested embedding model is missing in local Ollama.") from None
    return lambda texts, query: request(
        "/api/embed", {"model": model, "input": texts, "truncate": False}
    )["embeddings"], {"model_digest": digest}


def ranking(rows, query, embed):
    reference = unit_vector(embed([query], True)[0])
    scoreable, unscored = [], []
    for record in rows:
        identifier = record.get("id") or record["source_record_id"]
        abstract = (record.get("abstract") or "").strip()
        item = {
            "record_id": identifier,
            "title": record["title"],
            "doi": record.get("doi"),
            "url": record.get("url"),
        }
        if not abstract:
            unscored.append({**item, "score": None, "reason": "missing_abstract"})
            continue
        content = record["title"].strip() + "\n\n" + abstract
        scoreable.append(
            ({**item, "input_sha256": hashlib.sha256(content.encode()).hexdigest()}, content)
        )
    scored = []
    for start in range(0, len(scoreable), 24):
        batch = scoreable[start : start + 24]
        vectors = embed([content for _, content in batch], False)
        for (item, _), raw in zip(batch, vectors, strict=True):
            vector = unit_vector(raw)
            cosine = math.fsum(x * y for x, y in zip(vector, reference, strict=True))
            scored.append({**item, "score": max(-1.0, min(1.0, cosine))})
    return sorted(scored, key=lambda item: (-item["score"], item["record_id"])) + unscored


def rank(project, query, backend, model, port, manifests, output):
    if not query.strip() or not 1 <= port <= 65535:
        raise ValueError("Supply a nonempty ranking query and a valid local Ollama port.")
    sources = []
    if manifests:
        rows, seen = [], set()
        for path in manifests:
            manifest, records = verify_bundle(path)
            sources.append(
                {
                    "manifest": str(path.resolve()),
                    "run_id": manifest["run_id"],
                    "truncated": manifest["truncated"],
                    "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
            for record in read_json(records):
                doi = (record.get("doi") or "").strip().lower()
                key = ("doi", doi) if doi else (manifest["provider"], record["source_record_id"])
                if key not in seen:
                    rows.append(
                        {**record, "id": f"{manifest['provider']}:{record['source_record_id']}"}
                    )
                    seen.add(key)
    else:
        from .config import load_configuration
        from .service import ReviewService

        service = ReviewService(load_configuration(project))
        with service.db.connect() as connection:
            duplicates = service.duplicate_map(connection)
        rows = [
            {**json.loads(row["raw_metadata"]), **row}
            for row in service.records()
            if row["id"] not in duplicates
        ]
        sources.append({"protocol_revision": service.config.revision})
    model = model or (
        "BAAI/bge-small-en-v1.5" if backend == "fastembed" else "nomic-embed-text:v1.5"
    )
    embed, identity = embedding_backend(backend, model, port)
    result = {
        "schema_version": 1,
        "query": query,
        "backend": backend,
        "model": model,
        "embedding": identity,
        "sources": sources,
        "records": ranking(rows, query, embed),
    }
    save(Path(output), result)
    return {
        "output": str(Path(output).resolve()),
        "records": len(rows),
        "scored": sum(row["score"] is not None for row in result["records"]),
    }
