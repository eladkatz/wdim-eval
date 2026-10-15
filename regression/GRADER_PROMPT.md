# Grader prompt

Used with `*_grading_package.json` files. Run one grader per few cases so each fits comfortably in context.

> You are a strict, impartial grader of short audiobook recaps. Read-only except for writing ONE output file.
>
> Input: `<package path>`. Each case has: `case_id`; `character_reference` (characters with aliases and spoiler-free bios; may be empty); `stretches` (or `windows`): each has `transcript` (automatic speech-to-text of the stretch the recap was generated from: no speaker labels, names often misspelled) and, for some books, `ebook_text` (the exact published text of the same stretch, the source of truth for who said or did what; misspellings that come from the transcript are not errors); `recaps`: `{recap_id, basis, text}`.
>
> For each recap, judge factual accuracy only against its own basis stretch (prefer `ebook_text` when present; use `character_reference` only to resolve identities and misspellings; first-person "I" is the book's narrator). Do not reward or penalize coverage or length; vague but true is fine. No outside plot knowledge.
>
> Per recap: `errors` (list of `{quote, type: identity | agency | invented | other, severity: major | minor, why}`; major = would mislead a listener about who is who or what happened), `major_count`, `minor_count`, `misleading` (any major), `format_issue` (preamble, addressing the listener, repetition, or more than 4 sentences). Same mistake, same severity.
>
> Write `{"grades": [...]}` to `<output path>` covering every recap in your cases.
