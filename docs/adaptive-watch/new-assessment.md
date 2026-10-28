# New assessment

Runs a real assessment from the browser, through the existing backend. It needs a one-time gateway sign-in:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch.ps1 -AssessmentLogin
```

The launcher asks for the Hafnia gateway password in that window. It is held in the server process only. It is never
sent to the browser and never written to a file or log. Without it, **New assessment** explains what is missing and
nothing is submitted.

## Stages (all shown live in the dialog)

1. **Recording.** Acquires the latest 15 s of `person_on_railway_tracks` from XProtect (read-only, `acquire_recording.ps1`),
   as 0.5 s snapshots plus an MKV. The interval ends at least 90 s ago and lies inside the retained recording.
2. **Continuity.** The camera replays a 15 s clip on a loop, so a window can contain a restart. An automatic check flags an
   isolated jump. It cannot prove there is none, so you watch the recording and confirm.
3. **Local vision.** The exact local runner files are copied to p022-linux, run on the A10G, and the output's file hashes
   are checked against the local files.
4. **Hafnia.** One request, claimed in a per-job ledger before it is sent. A repeated click returns the same job. A claim
   without an answer is never re-sent; it is only polled. Quota is read from the gateway before the first submit.
5. **Matching.** Builds the same case view as the saved cases: footage, detector trigger, Hafnia answer, the XProtect
   handoff.

A failed stage stops the job with the reason and the next useful action. An unfinished job is never shown as a result.

## Status

The recording, continuity pre-check and GPU stages were run live on 28 Oct 2026 (window 11:01:32 to 11:01:47 UTC, A10G,
30 frames in 2.6 s). The Hafnia and matching stages are covered by unit tests with fakes. **The first live Hafnia request
needs the operator to start the server with `-AssessmentLogin`.** Native sending for a live result works the same way as for
the saved case once its review request is saved.
