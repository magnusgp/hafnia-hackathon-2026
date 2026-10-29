# Ortru: narration script (about 3 minutes)

Spoken pace about 150 words per minute. Roughly 450 words. Each block lists the slide it sits on and the deck step to press.
Read it in your own voice; do not claim anything the screen does not show. No speech has been synthesized and no video exists
yet: the owner records it (see [recording.md](recording.md)).

**Slide 1 · title (0:00–0:12)**
Ortru. In Greek myth, Orthrus is the two-headed hound that guards the herd. Ours has two watchers: Hafnia, and independent local
vision.

**Slide 2 · one assessment can miss it (0:12–0:35)**
This is a real case. A person sits on a platform edge and a few seconds later climbs down onto the tracks. Hafnia read the footage
and answered: no entry onto the track area is visible. That answer is on record, unchanged. It is an AI assessment, and on its own
an operator would have moved on.

**Slide 3 · second observer (0:35–0:55)**
A detector on a Linux GPU kept its own record of the same footage. It placed the person at the platform edge from the
fourth second. That is proximity, not entry. The two do not contradict each other; they are two observers, and Ortru keeps them
apart on one timeline.

**Slide 4 · what Ortru does (0:55–1:10)**
Ortru connects both to XProtect and applies a policy you define. When the two signals call for a look, it raises an exception.

**Slide 5 · create a Watch (1:10–1:35)**
A Watch is how you point a guardian at a camera. Pick the camera from the real XProtect catalog. Write what Hafnia should look for.
Choose local vision from a registry of capabilities that actually run. Draw the region on the camera picture. Set the policy, how
often to look, and a daily budget. No code.

**Slide 6 · configurable (1:35–1:55)**
Here are two Watches on two cameras: a platform and a school gate. Each has its own question, region and cadence. The gate camera
has no alarm in XProtect yet, and Ortru says so instead of offering a send button that cannot work.

**Slide 7 · monitoring (1:55–2:15)**
Monitoring works over recorded windows. Ortru checks the footage is still retained, reads it, runs local vision, asks Hafnia once,
never twice, and compares the answers. This samples recordings; it is not live streaming.

**Slide 8 · operator screen (2:15–2:35)**
The operator sees exceptions in a queue. The footage is large, with the detector box only at the moments the detector saw the
person. Hafnia is labelled an AI review. The human decision is the operator's, and it is recorded separately.

**Slide 9 · handoff (2:35–2:50)**
When the operator confirms, one real event goes to XProtect, once. The Event Server accepting it and Smart Client showing the
alarm are two different facts, and Ortru reports them separately. Both alarms from our earlier tests are listed in Smart Client.

**Slide 10–11 · limits and close (2:50–3:05)**
These are controlled scenarios: no accuracy benchmark, no production claim. What is new is a way to stop one assessment from being
the last word. Ortru. Two watchers, one guardian.
