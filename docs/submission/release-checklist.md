# Release checklist

**Submission deadline: Monday, 2 November 2026 at 11:00 CET.** Aim to be ready on 1 November. The video must be strictly under 180 s.

Done (evidence in `release-manifest.json`):
- [x] Release branch pushed to origin (no force push)
- [x] Python tests, TypeScript check, production frontend build
- [x] Film inspected: 173.16 s, 1920x1080, 25 fps, H.264 + AAC, burned-in captions
- [x] Live continuity finding recorded; interval chooser stops 2 s before the loop restart
- [x] AI-review provenance kept; continuity confirmation no longer attributed to a person

Waiting for the operator:
- [ ] Approve a native-path change or one new uniquely identified test event to isolate the Smart Client camera-preview defect
- [ ] Re-record the XProtect segment of the film if the preview is repaired; otherwise keep the accurate Alarm Manager segment
- [ ] Team approves the final film, then publishes it
- [ ] Merge to `main` (reviewed pull request)
- [ ] Team names, contact details and public video URL in `form-copy.md`
- [ ] Submit the form
