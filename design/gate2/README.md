# Gate 2: operator experience prototypes

Two compositions of the same product, built on the real Ortru records. They are design prototypes, not the application:
they contain no request code, save nothing and send nothing. The running application (port 8790) is untouched.

| | A · Console | B · Studio |
| --- | --- | --- |
| Idea | Exception list on the left (the Alarm Manager habit), one large investigation stage | Video first. The queue shrinks to a strip, a story rail beside the footage follows playback |
| Signals | Horizontal timeline under the video: three rows (Hafnia, vision, reviewer) | Three thin stripes under the video; the claims are a vertical story that lights up as the clip plays |
| Decision | Under the footage, left | Under the story, right |
| Watches | Dense table with small frames | Rows with larger frames |
| New Watch | Right-hand panel with all three decisions visible (open one, others summarised) | Wizard: one decision at a time, camera filmstrip, big frame |

## Open them

The prototypes read generated, git-ignored data (footage, camera frames, review text from the private runs). Generate it from
the running application (GET requests only), then open the files directly; no server is needed:

    .venv\Scripts\python.exe -I design\gate2\build-data.py        # reads http://127.0.0.1:8790
    start design\gate2\index.html

States worth opening: `a.html#/exceptions`, `#/exceptions/history`, `#/exceptions/evidence`, `#/exceptions/alert`, `#/watches`,
`#/watch/w-c95bfc089f?step=2`, `#/watch/new`, `#/watch/new?cam=busy_street` (no frame yet). Append `?seek=4.9` to an exceptions
URL to start the clip at a given second. Keys: space plays, arrows step half a second.

## Check them

    cd frontend
    bun ..\design\gate2\shoot.mjs a <outDir>      # every state at 1440x900 and 1920x1080 (PNGs hold footage: keep them private)
    bun ..\design\gate2\interact.mjs a            # 33 browser checks: play, seek, form rules, drawers, region drag, New Watch

## What is real and what is not

* Real: the occurrence (four assessments of one visual event, grouped by the server's `event` key), Hafnia's answer and its
  stated limit, the 24 detector samples and the box drawn from them, the recording, the evidence frames, the review revisions
  (revision 1 shown as the gap it is), the three Watches with their real states and last results, the camera frames.
* Overlaid: alarm 10 shown as verified in Smart Client. The product owner confirmed it on 30 Oct (recorded in the private
  evidence); the running application still reports `smartClient: not_verified` because nothing records that outcome yet.
* Reworded: the server's `policy.label` and `reason` ("Hafnia saw no match, local vision did") name the two sources, not what
  each claimed, so the prototypes write the reason from the policy kind. Job error text is rewritten in plain words (the
  school-gate message reaches the UI with a corrupted dash: `12?17 second`).
* Design states, not wired: "Get a frame" and its failure message, saving a Watch, activating, recording a review, sending
  an alert again.
