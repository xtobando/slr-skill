"""OpenAlex seed expansion built on the existing verified search archive."""

import re
from uuid import uuid4

from .archive import read_json, save
from .service import search


def snowball(project, seed, direction, limit, allow_credentials):
    if not re.fullmatch(r"W[1-9][0-9]*", seed):
        raise ValueError("Provide a verified OpenAlex work ID such as W1234.")
    if not 1 <= limit <= 1000:
        raise ValueError("Citation cap must be 1–1000 per direction.")
    round_id = f"citation-{seed}-{uuid4().hex[:10]}"
    manifests = []

    def collect(label, expression, maximum):
        result = search(
            project,
            "openalex",
            f"filter:{expression}",
            max_results=maximum,
            run_id=f"{round_id}-{label}",
            allow_credentials=allow_credentials,
        )
        directory = project.resolve() / "data" / "searches" / result["run_id"]
        manifests.append(
            {
                "role": label,
                "manifest": result["manifest"],
                "directory": str(directory),
                "status": result["status"],
                "stop_reason": result["stop_reason"],
            }
        )
        return result, directory

    if direction in {"backward", "both"}:
        result, directory = collect("seed", f"openalex:{seed}", 1)
        if result["status"] == "completed" and result["records_count"] == 1:
            response = read_json(directory / result["pages"][0]["file"])["response"]
            ids = list(
                dict.fromkeys(
                    match[1]
                    for value in response["results"][0].get("referenced_works", [])
                    if (match := re.fullmatch(r"https://openalex\.org/(W[1-9][0-9]*)", value))
                )
            )
            manifests[-1]["references_indexed"] = len(ids)
            manifests[-1]["references_requested"] = min(len(ids), limit)
            manifests[-1]["reference_cap_applied"] = len(ids) > limit
            ids = ids[:limit]
            for offset in range(0, len(ids), 100):
                group = ids[offset : offset + 100]
                collect(f"backward-{offset // 100 + 1}", "openalex:" + "|".join(group), len(group))
    if direction in {"forward", "both"}:
        collect("forward", f"cites:{seed}", limit)
    path = project.resolve() / "data" / "searches" / f"{round_id}.json"
    result = {"round_id": round_id, "seed": seed, "direction": direction, "runs": manifests}
    save(path, result)
    return {**result, "round_manifest": str(path)}
