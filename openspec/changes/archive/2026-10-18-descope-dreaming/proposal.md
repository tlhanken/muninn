# Descope Dreaming

## Why

The `dreaming-pipeline` change (Pass A session review, Pass B synthesis, Pass C
janitorial, `_Dreaming/` candidates) was proposed but never built. Offline consolidation
is now being redesigned from first principles for the next Muninn, which replaces the
file formats this pipeline was written against. Finishing it in this version would build
on formats that are about to be retired.

Leaving it open also has a cost today: the unbuilt pipeline's formats leak into the rest
of the corpus. About half of `memory-interfaces` pins dream-candidate and dream-log
formats that nothing writes, the writable page-type set includes `dream-candidate`, and
the living spec justifies session indexing by "the dreaming cron."

## What Changes

- Archive `dreaming-pipeline` **unapplied**, with a note at the top of its proposal saying
  it is deferred to the redesign. Its requirements never reach the living specs.
- Remove dreaming from the scope of `memory-interfaces` (candidate frontmatter, the
  `_Dreaming/` directory, the dream log, and candidate write ownership). That change is
  rescoped in the same series.
- `dream-candidate` stops being a writable page type. The type-set change itself is made
  by `memory-interfaces`, which owns the set; existing files with that type still parse.
- Reword the living spec where it refers to the dreaming cron or uses `Dreaming/` as an
  example.

## Non-Goals

- Designing any replacement consolidation for this version.
- Moving or deleting dreaming directories in the vault. Nothing here touches user data.

## Impact

- **Specs**: `qmd-wiki-memory-provider` (two requirements reworded, no behavior change);
  `dreaming-pipeline` archived unapplied; `memory-interfaces` rescoped.
- **Code**: one comment in `__init__.py`. No behavior change from this change alone.
