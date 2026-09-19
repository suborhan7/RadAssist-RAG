# Input Admission and Modality Gate — Architecture Specification

**Document status:** Version 1.1. **FROZEN at Gate A on 18 August 2026.**
**Supersedes:** Version 1.0, frozen 17 August 2026.
**Writing standard:** ASD-STE100 Simplified Technical English.
**Scope reference:** Defect P0-1, and the frontal-only scope finding of 18 August 2026.

**Why version 1.1 exists.** Version 1.0 described a repository state that was partly not correct. It also assumed that the archive holds both projections. The archive holds frontal images only. This version corrects both problems.

**What changed and what did not.** The existing service architecture is retained. No service is added, removed, renamed, merged or split. Version 1.1 adds admission and projection controls inside those service boundaries. Two of these controls are architectural, not editorial: DR-4 adds a declared-projection branch at admission, and DR-5 adds a post-retrieval projection-mismatch branch. The pipeline of section 9 therefore has two decision points that version 1.0 did not have.

**Changes from version 1.0:**

*Corrections of fact.*

- S3 said that a server-rendered disclaimer template exists. It did not exist. The implementation built it. See S3.
- S6 and S7 named a D4 migration. No such migration exists. See S6.
- M4 did not name a softmax temperature. Without a temperature the provisional threshold is unreachable. See M4 and M4a.
- Section 11.2 Step 2 told the reader to put lateral images in the positive set. This instruction produced a mixed calibration population. See Step 2.

*New scope decision.*

- DR-4 is new. The system accepts frontal chest radiographs only.
- DR-5 is new. The system uses two thresholds on the top-1 similarity, not one.
- Section 5.5 is new. It specifies the declared projection.
- Section 6.2 is new. It specifies the projection mismatch check.

*Corrections of measurement.*

- The lateral false-negative rate leaves the headline gate performance. Lateral inputs are out of scope.
- The 15 high-agreement cases are not evidence of an evidence conflict. All 15 are lateral. See 7.1.
- `RETRIEVAL_FLOOR` returns to the Gate B state. Its version 1.0 value came from a mixed population.

*Other.*

- Section 16 is new. It records the dataset limitations.
- The hardcoded projection metadata defect is recorded. See section 15.

*Corrections from the v1.1 draft review, 18 August 2026.*

- T2 is removed. It said that a lateral image passes all checks, which contradicts DR-4. T15 tests the correct behaviour.
- T16 is conditional. A lateral image must pass control M5 before it can reach control M10. T16a records how many do.
- Step 6 no longer proposes a lateral prompt. See Step 6.
- Step 3 now requires two denominators. See Step 3a.
- DR-4 Reason 1 no longer attributes a clinical opinion. That opinion is not recorded in this project. See DR-4 Reason 1a.
- M4b names the effective logit scale, after the exponential parameterization.
- Step R1 requires the percentile rule before the floor value.

---

## 1. Purpose

This document specifies two new services.

The first service checks the uploaded file. It finds unsafe files and damaged files.

The second service checks the image content. It finds images that are not chest radiographs.

The two services have different functions. Do not put them in one service.

---

## 2. Technical names

| Technical name | Definition |
| --- | --- |
| ImageAdmissionService | The service that checks the file bytes and the decoded image. |
| ModalityGateService | The service that checks if the image is a chest radiograph. |
| PrivacyService | The existing service that masks Protected Health Information. |
| EmbeddingService | The existing service that makes a BiomedCLIP vector. |
| RetrievalService | The existing service that queries ChromaDB. |
| Modality score | The softmax probability that the image is a chest radiograph. |
| Declared projection | The projection that the doctor selects at upload. |
| Projection reject threshold | The top-1 similarity below which the system rejects the image as not frontal. |
| Retrieval floor | The top-1 similarity below which the retrieval support is low. |
| Retrieval support | A category that shows how near the retrieved cases are to the image. |
| Agreement | The existing `VotedLabel.agreement` score. It shows how much the retrieved cases agree with each other. |
| Positive set | A set of held-out chest radiographs from the IU dataset. |
| Negative set | A set of images that are not chest radiographs. |
| Gate A | The architecture freeze. It occurs before implementation. |
| Gate B | The calibration freeze. It occurs after measurement. |

---

## 3. Vocabulary lock and the relation to decision D1

### 3.1 The problem

The word "validate" has three different meanings in this project.

1. The check of the raw uploaded file.
2. The check that the image is a chest radiograph.
3. The existing `validate_semantic()` function. This function compares the report with the retrieved evidence.

Decision D1 states the invariant "mask → validate → embed → retrieve". A reader can understand "validate" in D1 as meaning number 1 or number 2. This document puts the file check *before* the mask step. Therefore a reader can see a contradiction.

There is no contradiction. D1 refers to meaning number 2.

### 3.2 The lock

Use these three verbs. Do not exchange them.

| Verb | Meaning | Service or function |
| --- | --- | --- |
| **admit** | Check the raw file for safety. | ImageAdmissionService |
| **gate** | Check that the image content is a chest radiograph. | ModalityGateService |
| **validate** | Compare the generated report with the retrieved evidence. | `validate_semantic()` |

### 3.3 The corrected invariant

Write decision D1 in this form:

> **admit → mask → embed → gate → retrieve**

The admission step operates on the raw upload. It operates before the mask step, because the system must not send an unsafe file to the OCR library.

The gate step operates after the embed step. It uses the same vector. This order agrees with the original intent of D1.

**Action:** Add this corrected wording to the D1 decision record. Do not change the D1 approval status. The intent does not change. Only the words change.

---

## 4. Problem statement

The upload endpoint accepts all file types. It does not check the file bytes.

The pipeline accepted a photograph of a strawberry. The pipeline then made a full radiology report.

Two different controls are absent.

The first absent control is file safety. The system does not check the format, the size, or the decoded image.

The second absent control is a modality check. The strawberry image was a correct JPEG file. A file-level check alone does not stop it.

**Note:** The validation panel correctly showed the unsupported statements in the report. The output layer operated correctly. The input layer was absent.

---

## 5. ImageAdmissionService — requirements

The ImageAdmissionService operates before all other services. It operates on the raw upload.

### 5.1 Format checks

**A1.** Accept only these file name extensions: `.png`, `.jpg`, `.jpeg`.

**A2.** Read the first bytes of the file. Compare these bytes with the known PNG signature and the known JPEG signature.

**A3.** Do not use the `Content-Type` header to find the format. Do not use the file name to find the format.

**A4.** Reject the file if the signature does not agree with the extension.

### 5.2 Size checks

**A5.** Reject the file if the file size is more than the maximum size.

**A6.** Reject the file if the file size is less than the minimum size. A file of 4 kB is not a radiograph.

### 5.3 Decode checks

**A7.** Open the file with Pillow. Call `verify()`.

**A8.** Close the file. Open the file again. Call `load()`.

**Note:** `verify()` does not decode the pixels. A second open is necessary. This sequence finds damaged files.

**A9.** Set `Image.MAX_IMAGE_PIXELS` to a configured limit. This limit stops decompression-bomb attacks.

**A10.** Reject the image if the width or the height is less than the minimum dimension.

**A11.** Reject the image if the width or the height is more than the maximum dimension.

### 5.4 Normalization

**A12.** Encode the decoded pixels again as a PNG file. Use only the pixel array.

**A13.** Send only this new PNG file to the next service. Discard the original bytes after the pipeline completes.

**Note:** The new PNG file has no EXIF metadata. EXIF metadata can contain Protected Health Information. A polyglot file also becomes safe after this step, because the system keeps only the pixels.

### 5.5 Declared projection

**A14.** The upload request must hold a declared projection field. The permitted values are `PA`, `AP` and `LATERAL`.

**A15.** Reject the request if the field is absent. Do not select a default value.

**A16.** Reject the image if the declared projection is `LATERAL`. Use the reason code `DECLARED_LATERAL`.

**A17.** Reject at this point. Do not mask the image. Do not embed the image. Do not query ChromaDB.

**Note:** A radiographer knows the projection of the film. The requisition states it. A declared value is exact. A model prediction is not exact. Therefore the system asks, and does not predict.

**Note:** Requirement A16 is a fast rejection. It uses no GPU time. The check in section 6.2 finds the case where the declared value is not correct.

---

## 6. ModalityGateService — requirements

The ModalityGateService operates after the EmbeddingService. It uses the vector from the EmbeddingService.

**M1.** Do not encode the image again. Accept the existing vector as an input parameter.

**M2.** Calculate the cosine similarity between the image vector and each text vector in the prompt set.

**M3.** Use the prompt set in the configuration. See section 11.1 for the initial set.

**M4.** Apply softmax to the similarity values. The result for the chest radiograph prompt is the modality score.

**M4a.** Divide each cosine similarity by the softmax temperature before the softmax operation. Read the temperature from the settings object.

**M4b.** Set the default softmax temperature to the reciprocal of the model's **effective** logit scale, after the model applies its exponential parameterization.

**Warning:** OpenCLIP stores a learned parameter and applies an exponential to it before use. Do not divide by the stored parameter. Use `1 / exp(logit_scale_parameter)` if the stored value is the pre-exponential parameter. Read the model source and state which value you used.

**Note:** The measured effective value in this project is 85.2322769165039.

**Warning:** Do not apply softmax to raw cosine values. The measured raw values put radiographs at 0.228 to 0.232 and a photograph at 0.190. A threshold of 0.60 is then not reachable, and the gate rejects every input. Version 1.0 did not state this. This omission is the reason for M4a.

**M5.** Reject the image if the modality score is less than the modality threshold. See decision DR-1.

**M6.** Cache the text vectors at start-up. Do not encode the text prompts for each request.

### 6.1 The three bands

The system compares the top-1 similarity with two thresholds. The two thresholds make three bands.

**M7.** Read the top-1 similarity score from the RetrievalService.

**M8.** Find the band.

| Band | Condition | Action |
| --- | --- | --- |
| Reject | Top-1 is less than the projection reject threshold. | Stop. See section 6.2. |
| Low support | Top-1 is at or above the reject threshold, and less than the retrieval floor. | Continue. Set the support category to `below_floor`. |
| Normal | Top-1 is at or above the retrieval floor. | Continue. Set the support category to `at_or_above_floor`. |

**M9.** Set the retrieval support category for the second band and the third band. See section 7.

**Warning:** The two thresholds have different meanings. Do not join them into one value. A single threshold removes the low support band, and section 7 then has no function.

### 6.2 The projection mismatch check

**M10.** If the top-1 similarity is less than the projection reject threshold, stop the pipeline.

**M11.** Use the reason code `FRONTAL_MISMATCH`. Do not use the code `DECLARED_LATERAL`. Do not use the exception `NotAChestRadiographError`.

**M12.** The error message must not tell the doctor that the image is wrong. The message must ask the doctor to check the projection.

**Note:** A lateral image reaches this check only if the declared projection is not correct. A frontal image from a different hospital can also reach this check. The two causes give the same measurement. Therefore the message states a doubt, not a fact.

**Note:** The measured separation is: lateral maximum 0.8485, frontal minimum 0.8906, across 300 images of each projection. The two ranges do not overlap.

---

## 7. The evidence support signal

### 7.1 Two independent signals

The system holds two different signals about the evidence. They are not the same signal.

| Signal | Question | Source |
| --- | --- | --- |
| **Agreement** | Do the retrieved cases agree with each other? | `VotedLabel.agreement`, existing |
| **Retrieval support** | Are the retrieved cases near to this image? | Top-1 similarity, new |

**Warning:** These two signals can disagree. Five cases below the support threshold can hold the same label. The agreement score is then high, but the retrieval support is low. A disclaimer that reads only the agreement score will show high confidence for this case. This is the opposite of the truth.

**Retraction.** A previous report stated that this combination occurs in 15 of 600 held-out radiographs, and that the premise of section 7.1 is therefore measured. This statement is withdrawn. All 15 cases are lateral images. All 60 below-floor rows are lateral. Requirement A16 now rejects lateral inputs. Therefore the 15 cases show an out-of-scope input, not an evidence conflict.

**Status of the premise.** The combination of a high agreement score and a low retrieval support has not been observed in a frontal image. The premise stays a design assumption. Do not present it as a measured result.

**Rule.** The disclaimer must read both signals. Do not use one signal alone.

### 7.2 The support matrix

| | High agreement | Low agreement |
| --- | --- | --- |
| **Support at or above the floor** | Standard disclaimer. | The cases conflict. |
| **Support below the floor** | **No retrieved case meets the minimum retrieval-support threshold. The agreement score alone does not indicate strong evidence.** | No retrieved case meets the threshold, and the cases that the system retrieved do not agree. |

**S1.** Calculate the retrieval support category from the top-1 similarity and the retrieval floor.

**S2.** Give both the agreement score and the support category to the disclaimer template.

**S3.** Use the server-rendered parameterised template `evidence_disclaimer.py`. Do not add static text.

**Correction.** Version 1.0 called this template "existing". It did not exist. The disclaimer was one of the seven fields that the language model wrote. The implementation of 17 August 2026 built the template and moved the disclaimer from model-authored to server-authored. This is a change of behaviour, not only a change of wording. The thesis must describe the disclaimer as server-rendered.

**S3a.** The language model output schema now holds six fields, not seven. Check whether the generation evaluation harness scored the disclaimer field. If it did, the cleared BLEU, ROUGE, METEOR and CheXbert results were computed on a different artifact. Report the answer before the thesis states those results.

**S4.** The disclaimer for a low support category must state that no retrieved case meets the minimum retrieval-support threshold. It must state this in the report.

**Rule.** The disclaimer states only what the measurement shows. The measurement shows that the top-1 similarity is below the configured floor. The measurement does not show that the archive holds no similar case. A top-1 score of 0.52 with a floor of 0.60 is an example. A case exists, but it does not meet the threshold. Do not write a stronger claim than the measurement gives.

### 7.3 Persistence

**S5.** Store the retrieval support category and the top-1 similarity with the report. Store them at generation time.

**Note:** Decision D4 states that `voted_labels` and `agreement` must be stored at generation time. The reason for S5 is the same reason: the evidence state must not change after the report exists.

**Correction.** Version 1.0 assumed that a D4 migration exists. No such migration exists. No `voted_labels` column and no `agreement` column exist in the database. The implementation of 17 August 2026 wrote migration `a1f4c72b9e30`, which stores `retrieval_support` and `top1_similarity` only.

**S6.** The evidence snapshot is therefore not complete. Two of its four fields are stored. The other two are recomputed at read time by a frontend that already computes the agreement score a second way.

**S7.** Write a new gated migration for `voted_labels` and `agreement`. Do not modify migration `a1f4c72b9e30`, because it is applied. This migration blocks the next phase.

**Warning:** Until S7 is applied, a finalized report cannot be reconstructed. The disclaimer reads two signals. One signal is stored. Therefore nobody can show which disclaimer the doctor signed. For a clinical audit trail this state is worse than storing neither signal, because it appears reproducible and is not.

### 7.4 Frontend

**S8.** The backend calculates the retrieval support category. The frontend shows it.

**S9.** The frontend must not calculate the category from the raw similarity scores.

**Note:** The frontend already re-calculates the agreement score from the raw retrieved cases. This is a known defect. It can show two different numbers for one report. Do not repeat this pattern for the support category.

---

## 8. Decision records

### DR-1 — The modality gate blocks. It does not warn.

**Status:** Approved.

If the modality score is less than the threshold, the system stops the pipeline. The system does not make a report.

**Reason.** A report about a non-radiograph is a clinical safety failure. A warning depends on the doctor to read it. The strawberry defect shows that the system must not depend on this.

**Consequence.** The false-negative rate is not zero. The system will sometimes reject a true chest radiograph. Section 11.2 measures this rate. The thesis reports this rate as a known limitation.

**Consequence.** The system gives no override in version 1. An override needs a permission model and an audit design. Record the override as future work.

### DR-2 — The system records rejected uploads. It records metadata only.

**Status:** Approved.

**Record these fields.**

| Field | Reason |
| --- | --- |
| Timestamp (UTC) | Audit sequence. |
| Doctor identifier | Accountability. |
| Rejection reason code | Proof that the gate operated. |
| Stage of rejection | Shows which control operated. |
| Modality score, if calculated | Evidence for the calibration. |
| SHA-256 of the raw bytes | Finds repeated attempts. |
| File size in bytes | Diagnosis. |
| Declared extension | Diagnosis. |

**Do not record these fields.**

| Field | Reason |
| --- | --- |
| The image bytes | The image can contain Protected Health Information. |
| The original file name | **A file name frequently contains a patient name.** This is Protected Health Information. |
| The masked image | Do not keep either version of the image. |
| EXIF metadata | This metadata can contain Protected Health Information. |

**Warning:** The file name is a common source of a data leak. Example: `Abdur_Rahman_CXR_2026.jpg`. The system must not write the file name to the audit log, to the application log, or to an error message.

### DR-3 — A low retrieval support does not block. The report states the weak support.

**Status:** Approved.

If the top-1 similarity is less than the retrieval floor, the system continues. The report holds an explicit statement about the weak archive support.

**Reason.** Control M5 and control M8 find different problems. Control M5 finds a wrong input. Control M8 finds a correct input for which no retrieved case meets the support threshold. A rare condition is a correct input. The doctor needs this report.

**Consequence.** The system can make a report from weak evidence. Therefore requirement S4 is mandatory. The doctor must see the weak support in the report, not only on the screen.

**Consequence.** The disclaimer text now changes with the retrieval quality. See section 12.

**Policy summary:**

| Situation | Action |
| --- | --- |
| The input is not a chest radiograph. | Block. |
| The input is a chest radiograph. The archive support is weak. | Continue. State the weak support. |

### DR-4 — The system accepts frontal chest radiographs only.

**Status:** Approved on 18 August 2026.

The system accepts the projections `PA` and `AP`. It rejects the projection `LATERAL`.

**Reason 1, workflow.** The reporting workflow is scoped to frontal chest radiographs, `PA` and `AP`. A study usually holds a frontal image and a lateral image. When a doctor uploads a lateral image, the system asks for the frontal image of the same study. The doctor holds that file already.

**Reason 1a, pending.** A clinical opinion that the frontal view is sufficient for the conditions in scope has not been recorded in this project. Do not state such an opinion in this document or in the thesis until the supervisor confirms it and the confirmation is recorded in the decision history. DR-4 does not depend on it. Reason 2 supports DR-4 without it.

**Reason 2, technical.** The validated operating domain is a frontal query against a frontal archive. The archive holds 2,462 vectors. All of them are frontal. The retrieval evaluation used 576 frontal queries. The Phase 21 pool holds 477 frontal studies. A lateral input is outside every one of these.

**Note on the cause.** The frontal-only archive is not a defect. The file `ml/preprocessing/build_study_index.py` line 91 holds an explicit filter. Four documents record the decision. The defect was that admission did not apply the same scope to the input.

**Consequence.** The 162 lateral-only studies in the dataset cannot be reported. See section 16.

**Consequence.** Nothing in the frontal path changes. The archive, the embeddings and the index stay as they are. The Phase 20 results, the retrieval evaluation results and the Phase 21 pool stay valid.

### DR-5 — The system uses two thresholds on the top-1 similarity.

**Status:** Approved on 18 August 2026.

The projection reject threshold and the retrieval floor are two different values with two different meanings.

| Threshold | Question | Action below it |
| --- | --- | --- |
| Projection reject threshold | Is this image a frontal chest radiograph? | Stop. |
| Retrieval floor | How strong is the archive support? | Continue. State the weak support. |

**Reason.** One threshold cannot do both tasks. If a low support causes a rejection, the low support band disappears. Section 7, the disclaimer template, the `retrieval_support` column and the two-signal matrix then have no function.

**Reason.** The two bands hold different populations. The reject band holds lateral images and images from a different distribution. The low support band holds frontal images with weak archive support. Decision DR-3 exists for the second population.

**Consequence.** A frontal image below the reject threshold has no manual override in version 1. This agrees with DR-1. It is a real cost. Record it in the limitations.

---

## 9. Pipeline order

```
Upload  (file + declared projection)
  ↓
ImageAdmissionService  A1–A13     (admit)      → block: bad file
  ↓
ImageAdmissionService  A14–A17    (projection) → block: DECLARED_LATERAL
  ↓
PrivacyService (PHI mask)
  ↓
EmbeddingService (BiomedCLIP)
  ↓
ModalityGateService  M1–M6        (gate)       → block: not a radiograph
  ↓
RetrievalService (ChromaDB)
  ↓
ModalityGateService  M7–M12       (bands)      → block: FRONTAL_MISMATCH
  ↓                                            → or set support category
ContextBuilder → PromptBuilder → LLM
  ↓
evidence_disclaimer.py            (server-rendered)
  ↓
validate_semantic()               (existing, unchanged)
```

**Design decision.** The projection scope is applied twice. Requirement A16 uses the declared value and costs nothing. Requirement M10 uses the measurement and finds an incorrect declaration. The first check is fast. The second check is correct.

**Design decision.** The gate service has three entry points. The first uses the vector. The second and third use the retrieval scores. All three measure the suitability of the input.

---

## 10. Service boundaries and errors

Do not put the file checks in the PrivacyService.

Do not put the modality checks in the EmbeddingService.

Each service raises its own exception type. The API layer maps each exception type to an HTTP status.

| Failure | Exception | Reason code | HTTP status |
| --- | --- | --- | --- |
| Bad extension or bad signature | `UnsupportedImageFormatError` | `FORMAT_MISMATCH` | 415 |
| File too large | `ImageTooLargeError` | `FILE_TOO_LARGE` | 413 |
| File too small, damaged, or bad dimensions | `InvalidImageError` | `FILE_TOO_SMALL` and others | 422 |
| Declared projection is absent | `InvalidImageError` | `PROJECTION_NOT_DECLARED` | 422 |
| Declared projection is `LATERAL` | `LateralProjectionError` | `DECLARED_LATERAL` | 422 |
| Modality score too low | `NotAChestRadiographError` | `MODALITY_BELOW_THRESHOLD` | 422 |
| Top-1 below the reject threshold | `ProjectionMismatchError` | `FRONTAL_MISMATCH` | 422 |

**Rule.** `LateralProjectionError` and `ProjectionMismatchError` are separate exception types. Do not join them, and do not join either with `NotAChestRadiographError`. A lateral image **is** a chest radiograph. A joined type makes the rejection counts wrong.

**Note:** A low retrieval support is not an error. It has no exception and no HTTP status. See DR-3.

**Rule.** No error message contains the file name. See DR-2.

### 10.1 Message text

**Declared lateral, requirement A16:**

> Frontal view required. RadAssist reports frontal chest X-rays (PA or AP). Please upload the frontal image from this study.

**Projection mismatch, requirement M10:**

> This does not appear to be a frontal chest X-ray. RadAssist reports frontal views only (PA or AP). If this is a frontal image, it may differ from the reference archive. Please check the view and try again.

**Rule.** The second message states a doubt. It does not tell the doctor that the image is wrong. A correct frontal image from a different hospital can cause this message.

**Rule.** Translate both messages through the i18n key set. Do not write English text in the response body.

---

## 11. Gate B — calibration parameters

The values in this section are **not** part of the Gate A freeze. Nobody can select them before measurement.

### 11.1 Parameters

| Setting | Value | Gate | State |
| --- | --- | --- | --- |
| `UPLOAD_ALLOWED_EXTENSIONS` | `png,jpg,jpeg` | A | Frozen |
| `UPLOAD_MAX_BYTES` | 20 MB | A | Frozen |
| `UPLOAD_MIN_BYTES` | 20 kB | A | Frozen |
| `IMAGE_MIN_DIMENSION_PX` | 256 | A | Frozen |
| `IMAGE_MAX_DIMENSION_PX` | 8192 | A | Frozen |
| `IMAGE_MAX_PIXELS` | 80 000 000 | A | Frozen |
| `ACCEPTED_PROJECTIONS` | `PA,AP` | A | Frozen. See DR-4. |
| `MODALITY_PROMPTS` | See below | B | Selected |
| `MODALITY_SOFTMAX_TEMPERATURE` | 1 / 85.2322769165039 | B | Selected. See M4b. |
| `MODALITY_THRESHOLD` | 0.60 | B | **Selected on measurement.** See 11.3. |
| `PROJECTION_REJECT_THRESHOLD` | Not selected | B | Rule stated. See 11.4. |
| `RETRIEVAL_FLOOR` | Not selected | B | **Returned to Gate B.** See 11.5. |

Prompt set:

- `a chest radiograph`
- `a photograph of an object`
- `an abdominal radiograph`
- `a document or a scanned page`
- `a photograph of a person`

**Warning:** The version 1.0 value `RETRIEVAL_FLOOR = 0.7603` is withdrawn. It was fitted on a population that was half lateral. Requirement A16 rejects lateral images. Therefore that population no longer reaches the floor.

**Rule.** Do not write any parameter value in the source code. Put all values in the settings object.

### 11.2 Calibration procedure

**Step 1.** Make a positive set. Use held-out chest radiographs from the IU dataset. Do not use images from the ChromaDB index.

**Step 2.** Use frontal images only. **Do not put lateral images in the positive set.**

**Correction.** Version 1.0 Step 2 told the reader to include both projections. That instruction produced a calibration population that was half lateral. The modality threshold survives this error, because it rests on the negative sub-classes and the frontal false-negative rate. The retrieval floor does not survive it. See 11.5.

**Note:** A separate lateral set is still useful for one purpose only: to show that the modality gate does not call a lateral radiograph a non-radiograph. Report that measurement separately. Do not put it in the positive set that fits a threshold.

**Step 3.** Make a set of negative test classes. Include natural photographs, other radiograph modalities, scanned documents, and damaged images.

**Step 3a.** Report two denominators for each class: the count that reached the modality gate, and the count that admission rejected first.

**Step 3b.** Calculate the false-positive rate against the count that reached the gate, not against the count in the class.

**Warning:** A class that admission rejects entirely gives no evidence about the modality gate. The measured example is `damaged_image`: 0 of 20 reached the gate. A reader can take `0 of 20` as gate validation. It is not. Report both denominators so that no reader can make this mistake.

**Step 3c.** Do not report a pooled false-positive rate across the classes.

**Step 4.** Calculate the modality score for each image in the two sets.

**Step 5.** Calculate the false-positive rate and the false-negative rate at different threshold values.

**Step 6.** Evaluate lateral images separately, as a diagnostic check only. Do not use their false-negative rate to select the modality threshold. Do not add a lateral prompt to the prompt set unless a later architecture change supports lateral inputs.

**Reason.** Decision DR-4 puts lateral images outside the accepted domain. Requirement A16 and requirement M10 handle the projection. Measurement M3 shows that the prompt space separates anatomical classes poorly. A lateral prompt would add a text vector to the same collapsed region.

**Step 7.** Select the threshold against a stated false-negative budget. State the budget before you look at the results. Then select the threshold that gives the lowest false-positive rate inside that budget.

**Warning:** Do not minimise the false-negative rate alone. That rule degenerates. The measured false-negative rate reaches 0.0000 at a threshold of 0.01, and that gate admits 31 percent of the negative set. Version 1.0 Step 7 held this defect.

**Step 8.** Calculate the top-1 similarity for each image in the frontal positive set.

**Step 9.** Do not fit one floor for each disease label.

**Reason.** The measured label medians span 0.790 to 0.966, but every label's 25th percentile sits in a narrow band of 0.754 to 0.793. The medians differ by where the upper mass sits. The upper mass is frontal. Therefore the label ordering mostly measures the frontal and lateral mix of each label, not the evidence quality of that label. Fitting 18 floors to that would record a projection ratio as a clinical property.

**Note:** This rejection is not a result of inconvenient numbers. The variable is confounded. State this in the thesis.

**Step 10.** Record all selected values and all measured rates. This is the Gate B freeze.

**Rule.** Report the measured rates only. Do not write an improvement claim before the command output is available.

### 11.3 The modality threshold decision

**Selected value: 0.60. This value is selected on measurement, not on the freeze rule.**

The alternative value 0.82 was examined and declined.

| Effect of 0.60 → 0.82 | Measurement |
| --- | --- |
| `natural_photograph`, n=75 | 0 → 0 false positives. No change. |
| `other_radiograph_modality`, n=22 | 19 → 16 false positives. 73 percent still admitted. |
| Frontal false-negative rate, n=300 | 0.0000 → 0.0033 |

The change buys 3 rejections in the one sub-class that fails at either value. It costs 1 rejection of a true frontal radiograph. The only adequately powered negative sub-class is at zero at both values. Against the asymmetry in DR-1, the trade is declined.

> **Correction, 2026-08-19.** This paragraph previously read "costs 2 rejections of true
> frontal radiographs". The measured cost is **1**. The row directly above gives the frontal
> false-negative rate as 0.0000 → 0.0033 over n=300, and 0.0033 × 300 = 1, not 2; the single
> image is study 2115 (modality score 0.6544). Confirmed against
> `ml/outputs/calibration/threshold_rates.csv`, column `fnr_frontal`, at thresholds 0.60 and
> 0.82. The decision is unaffected — 0.60 is still selected, and the trade is still declined
> — so this is a narrative slip in a Gate B section, not an architecture change. The thesis
> should use 1. The same correction is recorded in the development log.

**Rule.** Do not report the lateral false-negative rate in the headline gate performance. Lateral inputs are out of scope. Report it separately, as evidence that the gate does not misclassify a lateral radiograph as a non-radiograph.

**Limitation.** The prompt set cannot separate a chest radiograph from another plain radiograph. The measured cosine between the chest prompt and the abdominal prompt is 0.827. This is the largest off-diagonal value in the 5 by 5 prompt matrix. The chest prompt is nearer to the abdominal prompt than to any intended contrast. More prompts will not correct this. A second stage is necessary, or the limitation stays.

### 11.4 The projection reject threshold rule

**Rule.** Select the midpoint of the observed separation gap. State that this is the rule.

Measured gap: lateral maximum 0.8485, frontal minimum 0.8906. The midpoint is 0.8696.

**Rule.** Report this value as an observed separation point. Do not report it as a validated frontal and lateral boundary. The measurement comes from 300 images of each projection from one dataset. It does not establish a universal cosine boundary.

**Step P1.** Confirm that the selected value rejects 300 of 300 lateral images and 0 of 300 frontal images.

**Step P2.** Report both counts in the thesis with the value.

### 11.5 The retrieval floor

**Status: not selected. Returned to Gate B.**

The version 1.0 value came from a population that was half lateral. That population no longer reaches the floor.

**Warning:** The frontal-only distribution may not support a fitted floor. The measured frontal values are: minimum 0.8906, 25th percentile 0.9589, median 0.9681, maximum 0.9880. There is no low tail and no separation. Any value inside that band is a chosen percentile, not a measured boundary.

**Rule.** If the frontal distribution gives no separation, do not invent one. Take these actions instead.

**Step R1.** State the lower-tail percentile rule **before** you calculate the resulting floor. Write the rule down first. Then apply it to the frontal calibration set and record whatever value it gives.

**Warning:** Do not look at candidate floor values and then select the percentile that gives a convenient one. That is the same defect as the degenerate rule in Step 7. The rule is the method. The number is the output.

**Step R2.** Report as a result that 0 of 300 held-out frontal cases fall below the value. State that the mechanism is not exercised in this distribution.

**Step R3.** State the purpose that the mechanism does serve: a distribution shift at deployment time. The calibration population and the archive share scanners, processing and patient population. A film from a diagnostic centre in Bangladesh does not. The IU dataset cannot measure this shift.

**Note:** This is a stronger position than a fitted number. It states what the measurement shows and what it cannot show. Record the unexercised state as future work.

---

## 12. Effect on Phase 21

Decision DR-3 makes the disclaimer text change with the retrieval quality.

Phase 21 compares three arms. The arms are different in the retrieval step. Arm A has no retrieval. Arm B has labels only. Arm C has the full pipeline.

Therefore the disclaimer text will be different for each arm. If the metric calculation includes the disclaimer, the disclaimer changes the metric. This is a confound.

**Action.** Add a rule to the Phase 21 document before the pilot run. The rule must state one of these:

1. Remove the disclaimer from the text before the metric calculation.
2. Use the same disclaimer text for all three arms.

This document does not select the rule. The selection belongs to the Phase 21 document.

---

## 13. Acceptance gate

The phase is complete only when all of these tests give real command output.

**T1.** A correct frontal chest radiograph passes all checks. The pipeline makes a report.

**T3.** The strawberry photograph fails at M5. The system shows the `NotAChestRadiographError` message.

**T4.** A text file with a `.png` extension fails at A4.

**T5.** A 2 kB image fails at A6.

**T6.** A decompression-bomb PNG file fails at A9. The process does not stop.

**T7.** A JPEG file with EXIF metadata passes. The normalized PNG file has no EXIF metadata.

**T8.** A rejected upload writes one audit row. The row holds no file name and no image bytes.

**T9.** An image with a top-1 similarity in the low support band makes a report. The report holds the weak support statement. **Note:** no frontal image in the calibration set falls in this band. Construct the case with a test fixture or an adjusted floor. Record which method you used.

**T10.** An image with a high agreement score and a low retrieval support makes a report. The disclaimer states the weak support. The disclaimer does not state high confidence. **Note:** the same constraint as T9 applies. All 15 observed cases are lateral and are now rejected. This test uses a fixture, not a real in-scope case.

**T11.** The report row holds the retrieval support category and the top-1 similarity.

**T12.** The calibration tables from section 11.2 exist with real numbers.

**T13.** The existing retrieval regression test passes after the change.

**T14.** An upload with no declared projection fails with `PROJECTION_NOT_DECLARED`.

**T15.** An upload with the declared projection `LATERAL` fails with `DECLARED_LATERAL`. The masker does not run. The embedder does not run. ChromaDB is not queried.

**T16.** A lateral image declared as `PA` that passes control M5 reaches retrieval. If its top-1 similarity is below the projection reject threshold, it fails with `FRONTAL_MISMATCH`.

**T16a.** Report how many lateral diagnostic images reach control M10, and how many control M5 rejects first. Control M10 cannot be tested on an image that control M5 already rejected.

**T17.** The exception for T15 and the exception for T16 are different types. The audit rows hold different reason codes.

**T18.** A frontal image is not affected by any control in section 5.5 or section 6.2.

**T19.** Both projection messages render in English and in Bengali through the i18n key set.

**T20.** The report row holds `voted_labels` and `agreement` after the S7 migration.

**T21.** The projection value in the ChromaDB metadata comes from the data row, not from a literal. See section 15.

---

## 14. Out of scope

- DICOM input support.
- Image quality checks, for example blur or incorrect exposure.
- An override control for a blocked upload. See DR-1.
- The PHI mask defect. See the separate document for P0-2.
- The non-determinism defect. See the separate document for P1.
- The Phase 21 disclaimer rule. See section 12.

---

## 15. Code defect to correct

**File:** `ml/retrieval/build_chroma_index.py`, line 142.

The projection value in the ChromaDB metadata is a literal string, not a value from the data row:

```python
"projection": "Frontal",
```

This value is correct today, because the filter at `ml/preprocessing/build_study_index.py` line 91 admits frontal rows only. It is correct by luck, not by construction.

**Rule.** Read the projection from the data row. If the archive ever holds another projection, the literal will report a value that is not true, and no test will find it.

**Note:** This correction does not change the current index contents. The value written stays `Frontal` for every current row.

---

## 16. Dataset limitations

**L1.** The dataset holds 7,466 images across 3,851 studies. The archive holds 2,462 vectors. Every drop is accounted for by a quoted line of code. There is no unexplained loss.

**L2.** 3,648 lateral images are excluded by design. See DR-4.

**L3.** 162 studies hold no frontal image at all. These studies cannot be represented in the archive, and they cannot be reported by the system. State this as a dataset limitation. The cause is the composition of the IU dataset, not a design choice.

**L4.** 129 surplus frontal images are dropped by the one-image-per-study rule. 129 studies hold more than one frontal image.

**L5.** The selection is deterministic. The sort key is `(uid, filename)` and the pairs are unique across all 7,466 rows, therefore no tie exists.

**L6.** The negative calibration set is not adequate for a general claim. Only two sub-classes reached the gate with a usable count: 75 natural photographs and 22 other-modality radiographs. `damaged_image` gave 0 of 20 to the gate. `scanned_document` gave 1 of 23, because the rendered pages compress below the 20 kB minimum. Rebuild those two sub-classes at a realistic file size before any claim about documents or damaged files.

---

## 17. Freeze

| Item | Status |
| --- | --- |
| Vocabulary lock and D1 correction | Carried from v1.0 |
| ImageAdmissionService A1 to A13 | Carried from v1.0 |
| Declared projection A14 to A17 | New. Reviewed 18 August 2026. |
| ModalityGateService M1 to M6, with M4a and M4b | Corrected. Reviewed. |
| Three bands M7 to M9 | Changed. Reviewed. |
| Projection mismatch M10 to M12 | New. Reviewed. |
| Evidence support signal S1 to S9 | Corrected |
| DR-1 modality block | Carried from v1.0 |
| DR-2 metadata-only audit | Carried from v1.0 |
| DR-3 low support continues | Carried from v1.0 |
| DR-4 frontal only | New. Reviewed. Reason 1a pending supervisor. |
| DR-5 two thresholds | New. Reviewed. |
| Gate B calibration procedure | Corrected. Reviewed. |
| Acceptance tests T1 to T21 | Corrected. Reviewed. |

**All review items of 18 August 2026 are applied. No open architecture decision remains.**

**Frozen at Gate A on:** 18 August 2026.

**Gate B is not frozen.** `PROJECTION_REJECT_THRESHOLD` and `RETRIEVAL_FLOOR` have no selected value. Sections 11.4 and 11.5 select them from measurement.

### Rules after the freeze

**F1.** Do not change sections 5 to 10 during the implementation. Write a new draft for any change.

**F2.** `PROJECTION_REJECT_THRESHOLD` and `RETRIEVAL_FLOOR` are Gate B outputs. Sections 11.4 and 11.5 select them.

**F3.** Do not write a Gate B result into sections 5 to 10.

**F4.** Do not write any threshold value in the thesis before the calibration gives real command output.

**F5.** The Phase 21 document must select the disclaimer rule before the Phase 21 pilot run. See section 12.

**F6.** The S7 migration blocks the next phase. Apply it before any further work on the evidence snapshot.

### Follow-up items

These are implementation and evaluation tasks. They are **not** architecture decisions, and they do not conflict with the freeze.

1. **S3a — evaluation artifact check.** Did the generation evaluation harness score the disclaimer field? The language model now writes six fields, not seven. If the disclaimer was inside the scored string, the cleared BLEU, ROUGE, METEOR and CheXbert results were computed on a different artifact.
2. **L3 framing — documentation wording.** Are the 162 lateral-only studies a dataset limitation or a clinical scope limitation? One line in the thesis. The count is not in question.
3. **Production-path retrieval rerun — validation execution.** Decision D1 requires it after implementation. The masking step moved to before the embedding step. The 6 passing regression tests are a guard, not that rerun.
4. **DR-4 Reason 1a — pending supervisor.** If the supervisor confirms that the frontal view is sufficient for the conditions in scope, record the confirmation in the decision history. Do not add it to this document. DR-4 does not depend on it.
