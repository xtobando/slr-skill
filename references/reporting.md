# Synthesis, reporting, and recovery

- Run `{SLR} --project PATH report` and `audit`. Use the emitted export directory and audit outcome. The workbench writes deterministic PRISMA counts at the selected event cutoff, screening and extraction tables, a LaTeX table, bibliography, and a hash manifest. Report unresolved decisions, cap/coverage issues, unavailable reports, and missing study links. Explain whether counts refer to records, reports, or studies.
- Use approved evidence to draft narrative synthesis by research question, with citations, contradictory findings, and uncertainty. Preserve the distinction between a study's claim and the reviewer's interpretation. A PRISMA count export supports reporting; fill remaining checklist items and select the applicable flow diagram template for publication.
- Use `refresh-search MANIFEST` for a new run of the same verified query, then inspect coverage, import, and deduplicate. Record date-range or query changes explicitly as a new plan. Keep earlier decisions and snapshots. Rerank current candidates if requested.
- Use `backup` at milestones, `backup-verify ARCHIVE` to verify a copy, and `restore ARCHIVE NEW_FOLDER` for recovery. Review restored state and keep originals, archives, protocol and exports together. Store live papers and review data in the user's workspace.

Expand `{SLR}` to the locked uv command in [setup](setup.md), or its documented Python fallback. Resolve all other relative paths from the review workspace.
