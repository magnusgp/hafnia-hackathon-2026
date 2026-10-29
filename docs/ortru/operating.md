# Running Ortru on p022

Ortru runs on the hackathon Windows machine and is opened **inside p022** (Remote Desktop): the server listens on
`127.0.0.1` only.

```powershell
cd C:\Users\Administrator\dev\hafnia-ortru
powershell -ExecutionPolicy Bypass -File scripts\ortru.ps1                 # http://127.0.0.1:8790
```

| Option | Effect |
|---|---|
| (none) | Reads XProtect (read only), runs local vision on the A10G. The Hafnia step waits for a gateway sign-in. XProtect sending is off |
| `-Gateway` | Opens a window where the Hafnia gateway password is typed once. It is kept in memory only |
| `-NativeSend` | Allows one confirmed review event at a time to be sent to the Event Server (`127.0.0.1:9090`) |
| `-Prepare` | Rebuilds the private evidence archive from the operator state (read only against it) |
| `-Stop` | Stops this server by its own process. Other servers are never touched |

Ortru keeps its own state in `runs/ortru` (ignored by Git). It never writes to the earlier operator state, `runs/release/app`
or the review databases. The only shared file it appends to is the duplicate-send ledger, and only for a confirmed send.
Ports 8770, 8771, 8776, 8778, 8780, 8781 and 8782 belong to other instances and are refused.

## First use

1. **Watches > Create Watch.** Choose the camera, take a picture, write what Hafnia should look for, name the condition, draw
   the region, set the cadence, Save and activate.
2. The scheduler looks at the Watch's camera at its cadence. **Assess the latest window now** runs one immediately.
3. With a gateway session, an assessment that meets the policy appears in **Exceptions**. Open it, watch the footage, answer
   the question, and Dismiss, Confirm without alert, or Send to XProtect (preview, then confirm).

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests                      # Python suite
cd frontend; ..\runs\tooling\bun-windows-x64\bun.exe run build                # tsc -b, then vite build
cd ..; powershell -ExecutionPolicy Bypass -File scripts\run-ortru-check.ps1   # real Edge, isolated fixture server, 1440x900 and 1920x1080
```

The browser check starts `tests/ortru_fixture.py`: the real server, store, engine, policy and views with fake XProtect, GPU and
Hafnia effects and a test transport that records the Event Server POST in memory. It cannot reach the Event Server.

## Native XProtect

What exists in XProtect and what has been verified is in [native-xprotect.md](native-xprotect.md). Adding a camera's event and
alarm is a VMS change (`scripts/xprotect/setup_review_alarm.ps1`) and is done only with explicit operator approval; Ortru
never does it by itself.
