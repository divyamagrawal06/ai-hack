# Research update: verified paper reading and Jev wire contract

Updated 2026-10-24. This report supersedes the **access limitations** in the earlier [Jev evidence memo](../research/jev-evidence.md): network access subsequently changed and the papers below were fetched and read. Historical access failures remain useful provenance, not current claims that these papers are unread. Published results described here are the papers' results, **not experiments performed on this prototype**. No live Jev calls or clinical validation were performed for this research update.

## Source access and reading scope

| Source | Current access | Reading completed here |
|---|---|---|
| [You et al., Native Probability Outputs for Clinical Triage: An Evaluation of Calibration and Decision Accuracy, arXiv:2610.24692v1](https://arxiv.org/html/2610.24692v1) | HTTP 200; title and version verified | Main methods, results, discussion and limitations; appendix label/protocol and results material. |
| [Madrid-García and Merino-Barbancho, Jev in Medicine: A Benchmark Evaluation, arXiv:2609.34024v4](https://arxiv.org/html/2609.34024v4) | HTTP 200; version dated 10 October 2026 | Main methods, results, discussion, limitations and disclosures. |
| [Shankaranarayana, Runje and Jannink, Beyond Answer Confidence: A Controlled Audit of Self-Knowledge in a Black-Box Decision Model, arXiv:2610.01006v1](https://arxiv.org/html/2610.01006) | HTTP 200; version dated 1 October 2026 | Setup, main experimental design/results, discussion and limitations. |
| [CARE-Bench, arXiv:2608.03731](https://arxiv.org/html/2608.03731) | HTTP 200 | Full text fetched; complementary paper review assigned separately. No claim of complete reading by this report's author. |
| [DECIDE-AI, PMC9116198](https://pmc.ncbi.nlm.nih.gov/articles/PMC9116198/) | HTTP 200 with article text | Full text fetched for complementary workflow review. |
| [FUTURE-AI, PMC11795397](https://pmc.ncbi.nlm.nih.gov/articles/PMC11795397/) | HTTP 200 **browser-check challenge**, not article content | No article reading established by this response. |
| [Randomized public-use medical LLM study, Nature Medicine](https://www.nature.com/articles/s41591-025-04074-y) | HTTPS proxy CONNECT 403 Forbidden | Not retrieved on this retry; do not treat its user-supplied synopsis as newly verified here. |
| [Official TypeSafe primitives](https://docs.typesafe.ai/primitives) | HTTP 200 with documentation content | Question/response contracts, independence, composition, field references and usage examples. |
| [Official TypeSafe confidence](https://docs.typesafe.ai/confidence) | HTTP 200 with documentation content | Semantics, exact formulas, limitations of interpretation and suggested operational use. |

Temporary downloaded HTML/text is under `/tmp/clinic-current-*`; these are literature sources, not imported patient fixtures. No benchmark patient conversation was copied into the demonstration dataset. Dates, sample counts and metrics below are reported by the sources rather than newly reproduced. These three Jev papers are preprints, and vendor documentation is interface evidence rather than independent clinical validation.

## 1. Native Probability Outputs for Clinical Triage

### Methods that determine what the comparison means

The study evaluates Jev 1.13.0 against four general-purpose models under a **direct probability protocol**: each model receives the same patient prefix and four action descriptions and returns a distribution; the maximum-probability label is the action. Jev uses Choice; comparator probabilities are elicited as structured responses. Reasoning is disabled or minimized, with a 256-output-token cap for the general-purpose models. This is not a comparison against unrestricted clinical conversations or against the best possible version of every architecture (§§3.1–3.2).

CARE-Bench's public release contributes 925 decision points from 439 cases. The principal comparison uses 135 Public Test 1 decision points from **62 cases**; cases do not overlap between development, validation and test splits. Multiple points from the same case are dependent. The paper handles uncertainty with 2,000 paired **case-bootstrap** replicates, retaining all points from each sampled case (§3.3). The study is exploratory, not preregistered; labels and earlier results had been inspected. It excludes 134 controlled-access held-out points.

The four labels are Info, Self-Care/Monitor, Nonurgent Care and Urgent Care. Info means insufficient information for a care recommendation; Urgent Care combines urgent and emergency evaluation (§3.1, Appendix C). Consequently, this result cannot directly establish the clinic's required distinction between **same-day human review and immediate emergency guidance**.

A second experiment compares binary Choice with Noul using matched state, instruction, criteria and returned model version. Wording/order changes and one identical-request repeat assess sensitivity. Thresholds chosen on development data under false-positive constraints are then evaluated on test data (§3.4, Appendix D). This matters because changing from four actions to one sufficiency question is a change in task formulation, not merely an API-format change.

### Results relevant to design

| Finding | Published result | Implication |
|---|---|---|
| Action selection versus probability error | Jev macro-F1 **0.461**, fourth of five; lowest observed multiclass Brier **0.610**, versus 0.750 uniform and 0.730 development prior (Table 1, §4.1). | Lower probability error did not establish superior routing. ECE, Brier and route error must remain separate metrics. |
| Four-action clarification misses | Jev identified **3/37** reference clarification points; it identified **22/26** urgent-care points (§4.2). | A route classifier can recognize many urgent cases yet inadequately detect missing information. Explicit defer is necessary to test, not sufficient to assume safe. |
| Matched binary sufficiency | Choice and Noul each detected **36/37** clarification points, with **54/98** and **53/98** false positives; binary Brier 0.27624 versus 0.21466 (§4.2, Appendix D). | Increased detection is not unique to Noul. Separate sufficiency assessment substantially increases unnecessary clarification under this protocol. |
| Threshold transfer | Under a development false-positive cap of 10%, original Noul achieved test recall **26/37** with **15/98** false positives (§4.2). | A threshold meeting a development target need not maintain that target under shift. |
| Prompt/repeat sensitivity | Reversing order changed 5 Choice and 1 Noul decisions; alternate wording changed 17 and 15; one identical-request repeat changed 2 and 1 (§4.2). | Version questions and include stability checks; typed output does not mean deterministic output. |

The paper's secondary HealthBench analysis uses 453 full conversations with unique physician-majority emergency categories, excluding 29 ambiguous cases. Jev macro-F1 is 0.788 and Brier 0.299, but this is final-conversation category classification rather than official rubric scoring or observed clarification behavior (§§3.5, 4.4). Its more favorable performance does not cancel the CARE-Bench failure: the label semantics and available information differ. It also assigns the conditional category to 61/134 non-emergent conversations, illustrating a different workload trade-off.

### Limits and transfer

The study does not evaluate prospective outcomes, independent clinician adjudication of these predictions, or interactive clarification quality. The principal test has only 62 reconstructed cases; training exposure is unknown. Matched formulation experiments concern Jev alone and include just one identical-request repeat. Cost/latency depend on providers, configurations, tariffs and concurrency; they are not a deployment service guarantee (§6). Its historical price figures should not become current budget assumptions.

**Specification consequence:** retain direct Jev as a genuine comparison arm; evaluate direct-plus-defer and direct-plus-separate-sufficiency separately. Keep urgency and information sufficiency as separate dimensions in the application contract. Report additional review and clarification burden rather than declaring near-perfect sufficiency recall a safety success. Never let a clarification request defer an already-triggered emergency message.

## 2. Jev in Medicine

### Methods

Jev 1.13 is compared with GPT-6 Sol at medium reasoning and no reasoning across MetaMedQA (1,373 items), PubMedQA (500), DiagnosisArena-MCQ (915) and 34 scored NEJM Case Challenges (§§2.1–2.4). Jev receives one Choice question per item; the comparator gets the same instruction/content/options with a constrained answer schema and elicited probabilities. Prompts are unoptimized, one run is performed per condition, and **decomposed Jev assessments are not tested**.

PubMed abstract conclusions are removed to avoid revealing answers. NEJM images are replaced by captions and laboratory tables transcribed; reference labels are taken as published, without new clinical adjudication. MetaMedQA includes malformed, missing-answer and fictional-organ questions. The primary metric is top-1 accuracy using the returned answer; paired accuracy differences use bootstrap intervals and exact McNemar tests with Holm adjustment across four principal comparisons (§2.5).

Calibration, correct/error discrimination and selective prediction are distinct outcomes: ECE, AUROC, Brier and risk–coverage curves. The investigators compare accepted accuracy at comparable coverage, because the same probability threshold can select very different proportions for different models. They avoid unstable ECE/AUROC estimates for the 34 NEJM cases (§2.5).

### Results

- PubMedQA accuracy was 78.4% for Jev versus 78.2% for GPT-6 Sol with medium reasoning. The study was **not designed to establish equivalence**, so “similar point estimates” is the defensible interpretation (Table 2, §4.3).
- MetaMedQA accuracy was 74.8% versus 82.7%; DiagnosisArena-MCQ was 59.8% versus 82.4%. These diagnostic/knowledge tasks differ from the proposed administrative intake workflow and do not prove an LLM is required for routing (Table 2).
- Jev's MetaMedQA ECE was better: 0.063 versus 0.146. Yet at comparable coverage the comparator was as accurate or more accurate, and Jev's AURC was worse, 0.087 versus 0.070 (§3.3). Calibration alone did not imply superior selective automation.
- For complex DiagnosisArena cases Jev's correct/error AUROC was 0.645 versus 0.768. Its answers above probability 0.9 had 75.9% accuracy at 17.3% coverage (§3.3): a high model probability was not a clinical safety certificate.
- Jev selected “I don't know or cannot answer” for **17/162** cases where it was the reference answer; GPT-6 Sol medium selected it for 8.6% (§3.4). Neither model was told some questions might be unanswerable. Separate sufficiency questions and threshold-based detection of unanswerable items were not tested.
- Two Jev responses and one comparator response returned a label different from the maximum-probability option (§3.1). Preserve both selected label and distribution and apply a documented consistency rule; never silently rewrite a raw response and lose the discrepancy.

### Limitations and transfer

Single unoptimized prompts, original option order, one run per condition and unknown training exposure limit generalization. Public benchmarks may overlap, and images have been removed. Verbalized versus native probabilities are systems-as-deployed comparisons, not a controlled causal test of architecture. Jev and comparator timing use different access routes/concurrency. NEJM reader polls involve self-selected people of unknown expertise (§4.3).

The paper explicitly marks its findings preliminary: independent replication, clinical reference adjudication and run stability remain pending. It discloses extensive generative-AI assistance in research/analysis/writing; this does not invalidate findings, but reinforces the distinction between reading a report and reproducing it. No performance number is transferred to this prototype.

**Specification consequence:** no standalone diagnostic function. Keep direct Jev and decomposed Jev distinct. Require held-out risk–coverage and reviewer-workload comparisons; a better calibrated model may still deliver worse routing or less safe automation at the same workload.

## 3. Controlled Audit of Self-Knowledge

### Methods

The audit comprises about **575,000 calls**, 15 public datasets and six generated task families. It requests `jev-latest`, records returned `jev-1.13.0`, repeats each cell three times and primarily analyzes the mean distribution (§3). Its “confidence” metric is the **top-answer probability**, not the vendor confidence field; this distinction matters when comparing its numbers with SDK outputs.

Paired interventions hold a question fixed while changing relevant information: intent labels with no description, examples, names or swapped mappings; generated unknown facts versus future chance events; supporting paragraphs removed/added; policy facts edited/deleted/contradicted; and irrelevant context. It also probes popularity, fabricated entities and dated news, with later controls using realistic names or removed dates. Those latter comparisons are observational and can reflect surface cues rather than knowledge itself (§3).

Targeted Noul questions ask whether an answer is settled, supplied evidence is sufficient, or the model knows the answer. Metrics include SmoothECE, AUROC, entropy and total variation; intervals are item-clustered, or month-clustered for dated news. The paper explicitly treats tests as an **audit checklist**, not proof of access to an internal epistemic state.

### Results and critical controls

On familiar closed-choice tasks, confidence often tracks correctness. With no answer-relevant information the model can nevertheless assign up to 0.80 to a salient option; on news past an observed knowledge boundary confidence exceeds accuracy by 0.21–0.33. Recalibration based on earlier months does not close this gap (abstract and §4).

Separate “evidence sufficient?” questions distinguish complete versus incomplete evidence with AUROC 0.95, compared with 0.85 for top-answer confidence on the same items. “Outcome settled?” reaches AUROC 1.00, but tense itself can identify that constructed distinction. “Do you know?” initially appears effective, yet realistic names and removed dates undermine evidence for an advantage over answer uncertainty (Table 1, §§4–5). Consequently, sufficiency of this input is a more useful bounded target than a vague claim that the model “knows its limits.”

### Limitations

This is a case study of one closed model/version. Curated contrasts and surface cues limit external validity; sufficient-evidence questions were checked against length features but that does not rule out every cue. The knowledge boundary is an observed change point, not a verified training cutoff. Date removal can change a question's proposition, and provisional labels for 240 pairs came from one AI annotator following a protocol. Most tasks were forced choice. Follow-up answers were validated as **rankings**, not calibrated probabilities of a latent knowledge state. Complete clinical routing policies and cost-based utility were not evaluated; additional robustness work was exploratory (Limitations).

**Specification consequence:** test source sufficiency, contradictions, scope and current-versus-historical warning signs separately. Add wording and superficial-cue controls. Missing details cannot become routine simply because warning-sign probability is low. Decomposed judgments are useful hypotheses to test, not an oracle for missing knowledge.

## 4. Official documentation and exact HTTP contract

The [primitives documentation](https://docs.typesafe.ai/primitives) confirms Choice, Score and Noul answer shapes, independently evaluated questions sharing the same state, and the need for code or a second call when one answer depends on another. Question IDs identify responses but are not sent to the model; the instructions must state the complete question. Jev does not return arbitrary explanatory prose or evidence spans. Candidate sentence IDs and offsets must be generated by the application; selected IDs must be checked against original text.

The [confidence documentation](https://docs.typesafe.ai/confidence), “How confidence is calculated”, now verifies exact semantics:

- Noul returns `p(yes)` and no confidence field. An optional derived concentration is `abs(2*p - 1)`.
- For Choice with `n > 1`, `confidence = (pmax - 1/n) / (1 - 1/n)`. It rescales the highest option probability relative to uniform; two distributions with the same maximum can have identical confidence despite different runner-up structure.
- Score confidence measures distance from the modal level relative to a uniform baseline and floors it at zero. The returned score itself is an expected rubric position; averaging can conceal probability on both low and high urgency.

These are mathematical summaries of the model distribution, not validated probabilities of clinical safety. The documentation's generic threshold examples are not clinical thresholds for this clinic.

The following text-only contract is verified against official SDK source at commit `f36e68549ceca3191e5791e5f99ea1baa1a258b5`: [endpoint builder](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/endpoints.py), [transport](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/transport.py), [constants](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/constants.py), and [wire models](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_schemas/models.py).

```text
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer <runtime TYPESAFE_API_KEY>
Accept: application/json
Content-Type: application/json
```

Illustrative request shape, **not an approved or evaluated clinical prompt**:

```json
{
  "model": "<explicit requested model identifier>",
  "state": {"synthetic": true, "text": "<invented description>"},
  "questions": {
    "information_sufficient": {
      "type": "noul",
      "instructions": "<complete versioned assessment question>",
      "criteria": {"true": "<defined yes case>", "false": "<defined no case>"}
    },
    "route": {
      "type": "choice",
      "instructions": "<complete versioned direct classification question>",
      "criteria": {
        "routine": "<policy definition>",
        "same_day_review": "<policy definition>",
        "emergency_guidance": "<policy definition>",
        "defer": "<policy definition>"
      }
    }
  }
}
```

The response has `model`, `answers` keyed by the same question IDs, and `usage` token counts. A Noul answer is `{"type":"noul","noul":0.8}`. A Choice answer includes `type`, `choice`, `confidence`, and `probabilities` keyed by the declared options. `GET /v1/models` supplies available model metadata; a requested alias and returned identifier must both be recorded. This research verified source contracts, not live API access.

The adapter should validate required answer presence, matching types, exact allowed options, numeric type and finiteness, [0,1] bounds, normalization tolerance, selected-label consistency and response model metadata. Preserve rejected payloads in the synthetic audit without credential headers. A timeout, malformed response, missing API key or unknown model never becomes “routine.” Do not follow redirects that could disclose Authorization to an unexpected host; preserve TLS verification and the configured proxy. Time limits cover total attempts, and emergency guidance is outside the network path.

## 5. Architecture decision after reading

The evidence supports **testing** focused Jev assessments; it does not prove that decomposition is superior to direct classification. The triage paper provides a concrete counterweight to overclaiming: separating sufficiency increases detection substantially but imposes many unnecessary clarification requests, and binary Choice performs similarly to Noul on the decision metric. The diagnostic benchmark provides another: better calibration may not improve safe coverage. The controlled audit supports asking precise input sufficiency questions while warning against relying on model self-knowledge or superficial cues.

Retain all four arms: structured form plus human review; direct Jev with explicit defer; decomposed Jev composed by deterministic rules; and a structured-output LLM using equivalent assessments. Compare at matched case sets, policy semantics and reviewer capacity, with explicit batching, timeouts, model versions and threshold selection. Measure emergency misses, unsafe routine suggestions, unnecessary escalation, clarification burden, reviewer time and failures separately. No study here approves a clinical routing policy, clinic staffing assumptions, jurisdiction, supported population or acceptable error rate.
