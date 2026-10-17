# Handover prompt

Prepare to stop work so another contributor can resume without this conversation.

Check recorded state against actual files. Record untracked consequential reasoning as decisions or notes, preserve task/experiment validation artifacts and identify incomplete work. Do not manufacture completion to make the handover appear clean.

Summarize completed outcomes and their evidence. Explain the current stopping point, active or released work, remaining acceptance gaps, unavailable resources, known risks and failed approaches. For failures, retain the command, configuration, observed result and why repeating it blindly is unhelpful.

Choose an ordered next action with task ID, relevant path, exact check or procedure and expected outcome. Name any unresolved decision or authority requirement. Use `TEMPLATES/handover.md` for supporting detail, then close the session through `session close` with summary and at least one `--next`; include applicable `--blocker` and `--failed` fields.

The CLI generates `SESSION_HANDOVER.md`. Keep longer maintained explanations in project notes and reference them. Run an audit and report material failures honestly. A new contributor must inspect a fresh Understanding Report before acting.
