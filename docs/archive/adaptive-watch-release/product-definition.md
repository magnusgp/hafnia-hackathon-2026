# Product definition and design decisions

Adaptive Watch is a second-signal layer for Milestone XProtect. Hafnia reads recorded video and sometimes answers
"no" for something that deserves a look. Independent local vision (a person detector on the Linux A10G) checks the same
recording for one configured condition. When Hafnia says no and the detector sees the condition, Adaptive Watch builds a
review exception and hands it to XProtect, where the operator already works.

## Pass 1: what we removed

Compared with ordinary Hafnia summaries, scheduled summaries, bookmarks, event triggers and XProtect alarms, these
ideas were cut because XProtect or Hafnia already does them:

| Cut | Already done by |
|---|---|
| A second written summary of the clip | Hafnia summaries |
| Camera patrol and status dashboards | Smart Client views and the Alarm Manager |
| Incident lists, assignment, notes, closure | XProtect alarms |
| Scheduled checks and rule builders | Hafnia schedules, XProtect rules |
| Model scoreboards and accuracy charts | not a claim we can support |
| Four equal cards per case | replaced by one working surface |

What stays is the one thing none of them does: **compare Hafnia's answer with an independent visual signal and turn a
disagreement into an XProtect review exception that points at the right camera, recording and moment.**

- Operator: a control-room operator who already acts on XProtect alarms.
- Trigger: Hafnia returned a negative answer, and the detector has the configured condition in the same interval.
- Information needed: which camera and moment, what each signal said, and the footage at that moment.
- Result of acting: one Adaptive Watch review event on the source camera, raising a camera-specific alarm.

## Pass 2: two compositions, critiqued

**A. Film and handoff.** Footage dominates the left. Under it, three lanes on one clock (Hafnia, local vision, footage
review). The right column is a rail of the two signals ending in "What XProtect receives" with the action inside it.

**B. Full-bleed theatre.** Footage edge to edge with the headline and timeline laid over it.

Critique of B as a security-operations designer: text over the footage hides the evidence, the action competes with
the picture, and the timeline cannot show three sources without covering the scene. Critique of A: more chrome, but
every element answers a question the operator has (what did each system say, when, what do I send). Selected: **A**.

First rendered review also showed the original right panel read as "Hafnia was wrong". The panel was rebuilt so Hafnia and
local vision are two contributors, and the primary object on the right is the exception XProtect will receive.

## XProtect integration choice

- The native alarm workspace stays XProtect's. The browser interface is the visual investigation surface and is opened
  on p022 (localhost is local to that machine).
- Analytics Event over the documented Event Server protocol (XML, port 9090), with source camera and source time,
  ledger-protected so a send is claimed before the POST and never retried automatically.
- A Smart Client workspace plug-in (the SCWorkSpace sample) would embed views but needs a C# toolchain that is not on
  p022 and cannot show our lanes. Not built.
- A bounding box is added to the event only after its rendering in Smart Client has been checked against the recorded
  frame. The documented example shows normalised values; the protocol page does not state origin or timestamp binding.

## Evidence rules

- A detector box is drawn only on the frame it was measured. Missing detections stay missing; nothing is interpolated.
- Hafnia, local vision, the footage review and any human decision are kept apart with their own provenance.
- The footage review of the railway case was made by the Claude demo reviewer (an AI). It is labelled as such.
- Evidence is from controlled synthetic camera scenarios. No accuracy or false-negative claim is made.
