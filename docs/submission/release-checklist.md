# Release checklist

**Submission deadline: Monday, 2 November 2026 at 11:00 CET.** Aim to be ready on 1 November. The video must be strictly under 180 s.

Done (evidence in `release-manifest.json`):
- [x] Release branch pushed to origin (no force push)
- [x] Python tests (220, 16 skipped), TypeScript check, production build, browser checks (62 + 23 at 1440x900 and 1920x1080)
- [x] Smart Client preview defect resolved by restarting Smart Client; live, playback and alarm 5 preview verified
- [x] Film rebuilt: 177.0 s, 1920x1080, 25 fps, H.264 + AAC, burned-in captions; silence at 91-98 s fixed; Smart Client scene updated
- [x] OFL font notices in `THIRD_PARTY_NOTICES.md` and `presentation/fonts/licenses/`
- [x] AI-review provenance kept; continuity confirmation is not attributed to a person

Waiting for the operator:
- [ ] Approve updating the stale "preview unavailable" note in the operator's native status (`runs/release/app/native/status.json`)
- [ ] A person watches and listens to the film once (audio was checked numerically only) and approves it
- [ ] Publish the film (not done)
- [ ] Merge to `main` (reviewed pull request)
- [ ] Team names, contact details and public video URL in `form-copy.md`
- [ ] Submit the form
