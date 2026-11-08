# Addendum: returning to a topic

Design notes for the next increment. The first implementation plan still describes the shipped replay CLI.

## An editing session, revisited

An editor saves a conversation about an orchard's poor harvest. They pick the exchange about a late frost for a first cut and save the irrigation discussion for later. A month later they add a conversation with new measurements. They can see the new material, revisit the irrigation passage, and propose a second cut. The first cut still points to the exact passages and editorial decisions used to make it.

Today, gather writes the supplied inputs to the destination's `sessions.json`. Gathering only the follow-up into the same destination can remove earlier messages from the bundle. The current storyboard records selections, trims, redactions and a reason for each beat. It lacks the history needed to explain what changed between cuts.

## What to preserve

1. **Topic sources.** Adding a conversation extends a private topic. Adding the same snapshot again has no effect. If a live session grows or an existing message changes, retain the earlier source version for passages that reference it. Report what was added or changed. Repeated wording alone is insufficient grounds to merge two turns.
2. **Saved passages.** Save exact source wording with its speaker, harness, session, stable message IDs, source-relative boundaries and source version. Keep enough local context to inspect the selection after the original harness log expires. A passage can be saved without being used in any cut. Its editorial note explains what made it worth saving.
3. **Cut history.** Give each saved cut a revision. For each output passage, trace what the viewer sees to its saved source and the ordered edits applied to it. Record factual changes mechanically, including selection, omission, trim, reordering, condensation, tool counts and substitutions. Save the agent's or editor's reason for meaningful decisions at edit time. An old edit whose reason was never recorded stays unknown. Keep draft proposals distinct from operator approvals.
4. **Private review.** Provide a readable private comparison of source wording, output and reasons. Keep sensitive originals and substitution maps outside the public checkout and all render inputs. Preview and render continue through the same review check. Adding source material to a topic does not alter an approved cut. Selecting it for a revised cut subjects the revised output to review.

## What the viewer sees

“Output” means the material presented in the replay. A source excerpt, a compressed group of tool calls and an editorial summary can each have different provenance. Preserve that distinction and product names that matter to the story.

Use the current tool on real edits before deciding whether to build paraphrasing. Until then, use source wording, existing display modes and narration. If a specific passage presents a genuine problem that trimming cannot solve, the agent may briefly explain why a paraphrase could help. A suggestion does not authorize rewriting. If the feature is later introduced, require an explicit request or approval for that passage, retain the exact source beside the proposed wording and reason, and identify the paraphrase as editorial wording in the output.

## First implementation slice

- Adopt an existing private episode as the first cut of a topic. Preserve its source IDs, storyboard, redaction decisions and existing takes. Record only the history that can actually be recovered.
- Add a second synthetic conversation twice. Verify that the second import adds nothing, that unused passages from the first conversation are still available, and that the first cut resolves to the same reviewed scene.
- Select one new passage for a second cut. Verify that its private change report explains the difference, that it requires review, and that both cuts can be reopened after deleting the original synthetic harness logs.
- Keep storage and command syntax open until implementing this slice. No change to the existing episode is required to try the current release.
