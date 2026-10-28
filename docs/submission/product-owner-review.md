# Product-owner review guide

A hands-on review of the Adaptive Watch release candidate, on p022. About 20 minutes. You do not need to open logs, XML,
hashes or source code. Nothing here is required to be written down.

**Safe by design.** The review runs on its own copy of the case in `runs\review`. It cannot send an XProtect event
(sending is off), does not need the Hafnia gateway password, and cannot change the operator's saved state, the original
recordings, the Smart Client alarms or the server on port 8780.

## Start

In a PowerShell window on p022 (Remote Desktop):

```powershell
cd C:\Users\Administrator\dev\hafnia-hackathon-2026
powershell -ExecutionPolicy Bypass -File scripts\review.ps1
```

(or double-click `review.cmd` in the repository folder). It checks the release, starts the isolated demo, and opens two
windows: **Edge** with the application at `http://127.0.0.1:8781/#/railway`, and **Windows Media Player** with the film.
Switch between them with Alt+Tab or the taskbar. If port 8781 is busy the script says which port it used instead.

Hear the narration: the film is played on p022, so Remote Desktop must play sound on *your* computer (Remote Desktop
options, Local Resources, Remote audio, Play on this computer). Or watch it on your own computer: run
`scripts\review.ps1 -ExportFilm` (verifies the copy, then opens its folder) and copy the file through Remote Desktop
file transfer (select it, Ctrl+C, paste on your computer). No upload and no network service is involved.

The film alone: `scripts\review.ps1 -Film`, file `runs\release\adaptive-watch-submission.mp4` (177 s, burned-in captions).
First use of Windows Media Player shows a one-time setup window; it has already been completed on p022.

## 1. Watch the film

Watch it once through, with sound. Replay from the start any time: reopen it with `scripts\review.ps1 -Film`.

## 2. Starting state of the application

- The **Station platform** tab is selected; the other tabs are School gate at night, Sidewalk with scooter, Sidewalk with bin.
- The footage is paused at **11:03:44.5 UTC**, the moment the person detector first placed the person at the platform edge,
  with the detector box and the dashed region drawn over it.
- The right panel reads **Review the station platform** with three signals (Hafnia, Local vision, Footage review).
  The review has not been saved yet. A button reads **Send to XProtect review**.

## 3. What to try, and what should happen

| Try | Expected |
|---|---|
| Press **Play from the trigger** | The person sits on the edge, then climbs down onto the tracks about four seconds later. |
| **The climb** | Jumps to the moment the person reaches the track bed (11:03:48.3). |
| Click **Hafnia**, **Local vision**, **Footage review** in the right panel | The footage jumps to what that source said, and when. |
| The three lanes under the footage | Hafnia's one answer (no entry observed), the detector's samples (dots) and the reviewed phases (edge, then tracks). Click anywhere in a lane to seek. The ‹ › buttons step between detector samples. |
| Seek with the lanes, **Play**, pause, step | Video and lanes stay in step. |
| Toggle **Box** and **Region** | The overlays appear and disappear over the footage. |
| **Send to XProtect review** | A short form: what do you see in the footage, a note, and "I watched the relevant footage". Save it. The panel then says "Your review request is saved". |
| Reload the page (F5) | The saved decision is still there (kept in this review session only). |
| **Preview XProtect event** (appears after saving) | Shows the event, the camera and a fingerprint, with "Sending is switched off for this session". **Send event** stays disabled. **Nothing is sent to XProtect in this review.** |
| **Evidence details** | The saved sources behind the case. You do not need to read them. |
| Other tabs | Secondary examples: the school gate (Hafnia's two prompts disagree, snapshots only) and the scooter and bin (local vision measured how long they stayed; Hafnia agreed). They are not railway validations. |
| **New assessment** (top right) | Explains that it is unavailable because this session has no Hafnia gateway session. It never asks you for a password. In the full system it acquires the latest footage from the camera, runs the detector, asks Hafnia once and compares them. |

The footage review shown is by an AI (labelled as such), not a human.

## 4. What to evaluate

1. Is the purpose understandable immediately?
2. Do the video and controls feel natural?
3. Is the important event easy to find?
4. Is the handoff to XProtect clear?
5. Does the interface contain unnecessary information?
6. Is any interaction confusing or frustrating?

For notes, `scripts\review.ps1 -Notes` opens a private text file (outside the repository's tracked files, kept when you reset).
It is optional.

## Start over, stop

- **Repeat the workflow from the beginning** (forgets only this review's saved decision):
  `powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -Reset`
- **Stop** (stops only the review server, by its own process; other Adaptive Watch instances keep running):
  `powershell -ExecutionPolicy Bypass -File scripts\review.ps1 -Stop`
- Closing the browser or media player does not stop the server; `-Stop` does.

Neither command touches the operator's real saved state.

## What was and was not checked for you

Checked by machine: the film is 177 s, 1920x1080, H.264 with AAC audio and burned-in captions, and plays in Windows Media Player
on p022; the application loads all four cases with verified sources at 1440x900 and 1920x1080; the review decision persists inside the
review session and nowhere else; sending is refused while off. **Nobody has listened to the narration;** that judgment is yours.
