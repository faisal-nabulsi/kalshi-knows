# TODO (owners)

## Faisal
- [ ] Paste the Anthropic key for the product's own Claude calls (announcer lines): run `! read -s K && echo "ANTHROPIC_API_KEY=$K" >> ~/Desktop/hackathon/degen-oracle/engine/.env`
- [ ] Find a legal stream of the 1:25pm games (SF@SEA) for the projector (YouTube TV / Fox app / NFL+ / Hulu Live)
- [ ] Find out our presentation time slot
- [ ] Test push on your iPhone (Safari → site → Share → Add to Home Screen → open it → Enable alerts) at the 12:30 checkpoint

## Kevin (slides + demo picks)
- [ ] Slides (5 min): name, team, problem (streams are 20–60 s behind), live demo, Someone Knew, Dutch Book, how we built it, results, what's next. Template: dark, a single orange accent, big numbers
- [ ] Pick 2 Someone Knew case files to tell as stories (from docs/data/someone_knew.json around 1:30)
- [ ] Rehearse the talk timing

## Dugar (video + testing)
- [ ] 1:25–2:30: screen-record the stream + the Kalshi Knows site side by side, with a phone in frame, during the late games; capture at least one real spoiler moment
- [ ] Cut the 2–3 min demo video (shot list from Claude in VIDEO.md)
- [ ] Test the site on your phone (Android or iPhone)

## Claude agents
- [ ] web: docs/ PWA + 3D + push UI (Opus)
- [ ] live-engine: engine/ FastAPI + polling + detector + push + tunnel script (Opus)
- [ ] nfl-data: pipeline/nfl_* aligned plays↔Kalshi trades, lag stats, replay.json (Sonnet)
- [ ] dutchbook: engine/dutchbook.py + docs/data/dutchbook.json (Sonnet)
- [ ] someone-knew: pipeline/someone_knew* + docs/data/someone_knew.json (Sonnet)
- [ ] lead: AWS training (train/), results.json, integration, GitHub Pages, terminate AWS
