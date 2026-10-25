# Medical report extraction

This optional input path addresses the same administrative intake problem: bring documented context into a request, show its source, and let a human review it. The assignment only permits synthetic patient records. It does not require a medical-report dataset or clinical diagnosis.

## Try it

1. Start `Start Final Demo.cmd` and open http://127.0.0.1:8081. Install PDF support once with `python -m pip install -r requirements.txt`.
2. Set server-side `OPENAI_API_KEY` or save a key in `var/openai-api-key.txt`. The latter is Git-ignored and excluded from the submission ZIP. Keep it out of browser code and screenshots.
3. Expand **Start from a synthetic medical report**. Upload an invented PDF, PNG, JPEG or UTF-8 TXT, or choose one of the five supplied samples.
4. Confirm that the document is invented and may be sent to OpenAI. Click **Extract report**.
5. Compare source excerpts, values, units, dates and negations with **Open original report**. Edit the proposed notes if needed and confirm review.
6. Click **Use reviewed notes in a new request**. This starts a new form with quoted report context. Add what you need today, then answer current age, symptoms, urgency, timing and emergency questions yourself.
7. Click **Review with AI**. Local Qwen assesses the submitted description. Staff can open the reviewed report facts beside the local AI handoff and save their own review or override.

Uploads are limited to 4 MiB. PDFs must be unencrypted, 1–8 pages, with at most 50,000 extracted text characters. Plain text is limited to 20,000 characters. Handwriting and low-quality scans may fail; check the original and use typed intake if extraction is unavailable.

## Extraction, categorization and decision

- **Extraction:** OpenAI `gpt-4.1-mini-2025-04-14` reads the document and returns a strict JSON schema: facts, verbatim source quotes, page and time context. It does not decide the route. The UI shows the actual provider/model and timing. PDF and text quotes must match their source after whitespace normalization. Images and scanned pages are labelled as transcriptions needing visual review, not machine-verified quotes.
- **Categorization:** after a person reviews the notes and completes today's intake, the existing local Qwen3 4B Instruct model assesses the six administrative routing factors and selects source excerpts. Report upload does not replace those current-status answers.
- **Decision:** the team's versioned routing policy combines validated assessments with form answers and independent warning checks. Unclear or incomplete requests go to human review; emergency guidance remains independent. Staff can override with a reason. No new diagnosis, prescription or automatic real booking is produced.

The report is untrusted content. Its embedded commands cannot redefine the extraction schema. Source matching proves that a quotation occurs in the file; it does not prove that the model categorized or interpreted it correctly. Human review remains necessary. The historical sample deliberately demonstrates that a symptom recorded in 2024 is not automatically a current symptom.

## Training and tests

We did not train or fine-tune OpenAI or Qwen for this feature. We use pretrained models, a constrained extraction prompt, validation and human review. Five invented development samples were authored with expected values before their live calls:

| Sample | Selected checks |
|---|---|
| Routine clinic note, PDF | Age, dry-skin description, duration and source quotes |
| Laboratory results, PDF | Values and units retained; no invented diabetes diagnosis |
| Historical discharge, PDF | Old date, age at report and resolved/historical context |
| Scanned laboratory report, PNG | Values and units; clearly labelled visual verification |
| Embedded instructions, TXT | Clinical facts retained; injected route and potassium value excluded |

The first live run passed **5/5 disclosed sample checks**. These are selected development checks, not complete clinical annotation, external validation, sensitivity or general accuracy. They are not part of the earlier local-routing 28+8 regression results. Raw accepted extractions, model identity, token counts, source fingerprints and per-check outcomes are in `reports/generated/report-extraction-runs/`; the latest summary is `reports/generated/report-extraction-results.json`.

The automated suite passed **166/166 tests**, including 16 new report tests for consent, file bounds, malformed output, source verification, incomplete/refused responses, secret handling, review confirmation and immutable request provenance. The 12 regular browser checks also pass. `tools/browser_reports_check.py --execute` passed eight checks using real cloud extraction followed by local Qwen routing and staff review in an isolated database. Browser results are stored separately from API/unit results.

Known limitation observed in that additional live browser extraction: the model returned `missing_date` despite also extracting the report date. The review screen explicitly identifies this inconsistent flag and asks the person to verify it. This is preserved in the raw evidence; the five sample checks did not assert all issue labels. Passing those selected checks must not be described as perfect extraction accuracy.

```powershell
python -X utf8 tools/run_checks.py --output-dir reports/generated/report-feature-checks
python -X utf8 tools/browser_check.py --output-dir reports/generated/report-feature-checks
python -X utf8 tools/evaluate_reports.py --execute
python -X utf8 tools/browser_reports_check.py --execute
```

The last two commands make billable OpenAI calls using only the supplied invented reports. Omitting `--execute` performs no calls. The browser report check also calls the local Qwen model. Existing routing prompts and the frozen routing policy have not changed.

## Data and failure behavior

The optional upload goes to OpenAI, while normal typed intake and routing remain local. The API request uses `store: false`; this is not a promise of zero provider retention. CareRoute does not persist the uploaded bytes. It stores the accepted extraction, document SHA-256, provider/model and timing locally. A random report reference connects the extraction to the later request; the database stores its hash. The server attaches its saved extraction rather than trusting client-supplied provenance, and records a review-confirmation audit event. The original document is not available to staff after upload; they can inspect the preserved excerpts and ask the requester to show the original separately.

A provider failure, refusal, incomplete response or invalid quote produces an explicit failure and imports nothing. Only one report extraction is allowed at a time. Clear form and typed intake remain available. There is no fallback that silently invents report facts or claims local extraction when cloud extraction failed.

API integration follows the official [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs) and [file input guide](https://developers.openai.com/api/docs/guides/file-inputs).
