# Ortru: product definition

Ortru is a configurable video intelligence and exception-handling layer for Milestone XProtect and Hafnia VLM. It is named
after Orthrus, the two-headed guardian hound of Greek myth. The two watchers are **Hafnia**, which reads recorded video and
answers in words, and **independent local vision**, a detector on the Linux A10G that keeps its own record of the same
footage. Ortru connects them, applies a defined review policy, and sends actionable exceptions into XProtect, where the
operator already works.

It is not a second summarizer, an incident manager or a model comparison. Hafnia's answer stays on record. What Ortru adds
is a way to stop one assessment from being the last word.

## Three concepts

| | What it is |
|---|---|
| **Watch** | What the operator wants to guard on one existing XProtect camera: a question for Hafnia, a local vision check with an optional drawn region, an exception policy, a cadence and budget, and the native event mapping. Versioned: every edit is a new immutable version. |
| **Exception** | A real assessment (one recorded window of the Watch's camera) whose two signals meet the Watch's attention policy. |
| **Investigation** | The screen for one exception: source video, what each source established, why it was raised, the review question from the Watch, and the action that sends a review event into XProtect. |

## The two signals are separate observers

Local vision measures proximity (a tracked person's foot inside or near a drawn region). It does not confirm entry. Hafnia is
an AI reading of the footage, not a human review. The human review is the operator's own decision, recorded apart from both.

| Hafnia | Local vision | Meaning | Raised by default |
|---|---|---|---|
| not observed | person at the region | `disagreement`: a "no" next to a person at the hazard is not a contradiction | yes |
| observed | person at the region | `corroborated` | yes |
| unsure or unusable | person at the region | `unresolved`: never treated as "no" | yes |
| observed | nobody at the region | `hafnia_only` | no (a Watch can opt in) |
| not observed | nobody at the region | `clear` | no |
| unsure or unusable | nobody at the region | `inconclusive` | no |

## Two handoffs, kept apart

1. **Review decision** (local, auditable): the operator watches the footage, answers the question the Watch defined
   ("Is "Person on the track area" visible in the footage?"), and chooses Dismiss, Confirm without alert, or Send to XProtect.
2. **Native dispatch** (real): only for a saved decision, only to an XProtect destination that exists, only after the operator
   reviews the exact event (camera, source time, message, destination, fingerprint) and confirms. It goes through the
   claim-before-POST duplicate-send ledger and is never retried. The Event Server accepting the event and Smart Client showing
   the alarm are different facts and are reported as different states.

Where a camera has no XProtect alarm, review still works; the Watch page and the investigation say what is missing instead of
offering a send button that cannot work. Adding an event and an alarm to XProtect changes the VMS and needs explicit operator
approval.

## What Ortru does not claim

Ortru samples **recorded windows** at the Watch cadence. It does not stream live video. There is no accuracy benchmark, no
measured reduction in missed events and no production deployment. Evidence comes from controlled synthetic camera scenarios.
