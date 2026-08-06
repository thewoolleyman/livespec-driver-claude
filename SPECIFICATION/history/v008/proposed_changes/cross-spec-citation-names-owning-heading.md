---
topic: cross-spec-citation-names-owning-heading
author: claude-opus-5
created_at: 2026-08-06T11:24:57Z
---

## Proposal: Cite livespec core's owning heading rather than a paragraph label

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Change this Driver's three cross-spec citations of livespec core's
install-verification invariant from `§"Install verification"` to
`§"Plugin distribution"`, the heading that actually owns that content in core's
`SPECIFICATION/contracts.md`. Ownership of the invariant is unchanged; only the
section name used to point at it changes.

### Motivation

`§"Install verification"` is not a heading in livespec core. Core's
`SPECIFICATION/contracts.md` carries `## Plugin distribution`, and
"Install verification." appears inside that section as a leading paragraph
label, not as a heading of its own. The citation therefore names a section that
does not exist, and following it resolves to nothing.

This has been latent rather than harmless. `doctor-no-cross-spec-reference`
resolves a citation same-tree or through the `external_references` allowlist in
`.livespec.jsonc`, and this repository has carried an allowlist entry naming the
same non-existent section. While livespec was absent from this repository's
`cross_repo_targets`, the checker had no clone in which to resolve the reference
and the citation passed unexamined. Registering livespec as a cross-repo target
— required so the Dispatcher's readiness gate can resolve `sibling_work_item`
dependencies on livespec, which otherwise fail closed to UNKNOWN — gives the
checker that clone and the citation fails.

The registration is correct and must stay. The citation is what is wrong, and it
was wrong before the registration exposed it.

Measured on livespec `origin/master` at the time of authoring: core's
`SPECIFICATION/contracts.md` contains `## Plugin distribution`, and contains no
heading matching "Install verification". The install-verification rule this
Driver realizes — that a project is correctly provisioned only when the registry
holds an entry whose `projectPath` equals the project root — is stated inside
that section.

### Proposed Changes

In `contracts.md`, replace every occurrence of the section citation
`§"Install verification"` with `§"Plugin distribution"`. Three occurrences are
affected, in the paragraphs covering `projectPath` selection, the defective
enabled-without-installed state, and the recorded mechanism. No surrounding
prose changes: each sentence keeps its meaning, its attribution of the rule to
livespec core, and its framing of this Driver's step 3 as a realization of
core's invariant rather than a restatement of it.

At the FIRST occurrence — the paragraph establishing that selection is by
`projectPath` — the citation additionally names the owning paragraph in
apposition, as `§"Plugin distribution" (its "Install verification." paragraph)`.
`§"Plugin distribution"` is a broader target than the rule being cited, so a
reader following the bare heading lands on a long section rather than on the
specific invariant; naming the paragraph beside the heading restores that
precision at no cost to the citation checker, which resolves the heading only.
This is core's own established idiom for this rule, which core's committed
guidance already cites as `§"Plugin distribution" (install verification)`. The
remaining two occurrences take the bare heading, because each already sits in a
sentence that says which rule it means.

No heading in this specification is added, removed, or renamed, so
`tests/heading-coverage.json` needs no companion edit.

This change deliberately does NOT ask livespec core to promote its paragraph
label into a heading. That would also make the citations resolve, but it would
change core's heading set for the benefit of a single consumer — measured across
the fleet, this Driver is the only repository citing that section — and would
drag core's own heading-coverage map with it. Naming the owning heading is the
proportionate repair and keeps the correction inside the repository whose
citation is wrong.

The paired `.livespec.jsonc` edits ride with this change rather than in a
separate one, because the allowlist entry and the prose citation must name the
same section or the citation stops resolving: the `external_references` entry is
updated to `SPECIFICATION/contracts.md §"Plugin distribution"`, and livespec is
added to `cross_repo_targets`. Both are ordinary configuration outside the
governed specification tree.
