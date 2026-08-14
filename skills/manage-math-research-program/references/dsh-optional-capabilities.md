# Optional external capabilities (DSH conventions)

Vendor-neutral catalog of how the math-research skills use optional external
capabilities on DSH. This file is DSH-layer-owned (not synced from the Codex
parent). All listed plugins exist in the open-source DSH ecosystem; they
install through the deployment's profile-bundle mechanism
(`dsh plugin --profile <name> add github:<owner>/<repo>`, then restart the
profile). Verify a bundle against THIS deployment before use: community
compatibility targets are pinned to the public DSH release, and a local
checkout may differ. In this deployment the mechanism exists (profile
`dsh.profile.bundles` layer stack, pnpm reconciliation); the CLI binary lives
in the harness checkout rather than on PATH.

## 1. Vision for text-only models

Plugins:

- dsh-vision-toolkit (https://github.com/Anionex/dsh-vision-toolkit): ten
  structured tools - intent-aware image Q&A, long-screenshot OCR,
  original-pixel grounding, UI restoration, pixel diff verification,
  Artifacts, Web cards.
- dsh-vision (https://github.com/william-jin-cmu/dsh-vision): a single
  `view_image` tool bridging any OpenAI-compatible VLM endpoint
  (baseURL + apiKey + model).

Conventions:

- Never trust a vision answer as evidence. Treat VLM output exactly like
  `RECALLED_UNVERIFIED` memory: useful for orientation, but it must be
  re-checked against the primary source before entering any obligation.
- For math figures and scanned formulas, ask for a verbatim transcription
  plus the coordinates of every region read (grounding), then verify the
  transcription against the rendered source.
- Record the vision service, model, and any key used (by name only, never the
  secret) in repro_manifest.md.

Cost: a free tier exists (Zhipu glm-4.6v-flash with an automatic fallback
chain) or any OpenAI-compatible endpoint (DashScope qwen3-vl, Volcano doubao,
local Ollama qwen3-vl). The DeepSeek official vision API was not open as of
2026-08 (official wording: soon).

## 2. Document parsing (PDF/images to Markdown)

Plugins:

- dsh-plugin-mineru (https://github.com/HuanLinOTO/dsh-plugin-mineru): MinerU
  document parsing - PDF/images/DOCX/PPTX/XLSX to structured Markdown/JSON
  with formula support; async job polling; output above the inline cap goes
  to a file for the read tool.
- dsh-paddle-ocr (https://github.com/omdsh-dev/dsh-paddle-ocr): OCR-only.

Conventions:

- Run the parser before Phase 0 reading for scanned or layout-heavy papers;
  record parser + version + parse method (auto/txt/ocr) in repro_manifest.md.
- Parser output is unverified input: citations, formulas, and statements
  extracted this way must be re-checked against the original PDF page before
  any proof use (upstream Phase 0 item 9).
- Prefer the file-output path for long documents; keep the conversation lean
  and cite the output path + hash instead of pasting the full Markdown.

Cost: a MinerU service endpoint (self-hosted or API) or its VLM engine
backend.

## 3. When NOT to use them

- Skip vision/parser services when the base model already accepts images
  (the harness read_image tool) or the PDF has a clean text layer.
- Never let a VLM or parser settle a mathematical claim; they transcribe,
  they do not prove.
