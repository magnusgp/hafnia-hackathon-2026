# Deck media (private, not committed)

The deck uses real screenshots of the running application. They show camera frames of the hackathon scenarios, so they are
private and ignored by Git; slides fall back to a caption when a file is missing.

Create them on p022 with the real server running (`scripts\ortru.ps1`), from `frontend`:

```powershell
..\runs\tooling\bun-windows-x64\bun.exe scripts\shoot-real.mjs ..\presentation\ortru\media
```

Expected files: `1920-exceptions-record.png`, `1920-create-watch.png`, `1920-watch-station.png`, `1920-watch-gate.png`
(plus the 1440 variants). The script only navigates and draws on the page; it saves nothing and sends nothing.
