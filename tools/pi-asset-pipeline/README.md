# Isolated Pi screenshot-to-assets pipeline

## Inputs and fresh run
Only game description and screenshots are task inputs:
```sh
python3 run_pi.py --description game.md --screenshots frame1.png frame2.png --request-limit 8
```
`--prepare-only` creates a clean workspace without API calls. Every run lives in runs/<unique-id>/; previous scripts/assets/coordinates are not copied. Agent analyzes images, chooses references, creates inventory and implements reconstruction itself. Pinned local Pi 0.73.1; no global installation/DSH edits. Credentials resolved into inherited env, never stored in workspace. Models: cliproxy gpt-6.1-sol and gpt-image-2.

## Independent quality gates
Builder calls `python3 critic.py --stage geometry|assets|scene --manifest relative.json` in its run. Manifest: items with unique id and files listing source/candidate/evidence paths. Fresh Pi critic has ONLY read,grep,find,ls tools, no session/history, no bash/write/image generation. Reports and trace under output/critics. Builder repairs issues and re-reviews, maximum three reviews per stage, preserving image budget for corrections.

- Geometry BEFORE generation: alternative edge-class/phase hypotheses, source overlays and held-out floor/anchor evidence. Gridless/irregular scenes supported; no game-specific coordinates.
- Assets BEFORE accepted assembly: all variant/state/pose references and generated candidates; completeness versus source occlusion treated separately.
- Scene AFTER assembly: original versus reconstruction, inventory, registration, negative space, depth, UI and fidelity.

Image wrapper enforces current geometry pass for fresh gated runs. Launcher verifies all three hash-bound reports; process exit 0 alone does NOT imply accepted output. Overall exit 2 means provisional/unaccepted. Changes to reviewed artifacts invalidate acceptance. Asset/scene transitions rely on builder following TASK plus final launcher check; this is not an OS sandbox against malicious rewriting of files. Critics verify listed files were read and all listed ids covered; correctness/completeness of the builder's inventory still requires visual judgement.

## Image references and budgets
Two agent-selected images per object: contextual crop + masked crop. Grouped sheets use explicit reference_pairs for represented variants only. Never auto-attach the whole workspace to image API. Budget reservations use locking and an append-only image_requests.jsonl; interrupted submissions still count. No silent model fallback.

## Outputs and replay
Agent produces description, asset_map, geometry/overlays, references, generated images, sprites, registration, reconstruction/A-B, critic evidence and honest report; local replay script is agent-written and makes no API submissions. Historical output/ and rebuild_local.py belong to the old example only, NOT new run instructions.

## Verification scope
Four native critic contract checks in test_critic.py cover path containment, actual-read coverage, contradictory pass, stale artifact hashes and JSON extraction. Behavioral extractor returns 0 nodes, so no exhaustive coverage claim. Live critic smoke is run separately with critic_smoke.py against stored results, without image generation. Generality and improved end-to-end visual fidelity require fresh runs on multiple games; do not infer them from one example.
