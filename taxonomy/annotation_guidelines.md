# Annotation guidelines

**Applies to taxonomy version 1.0** (`taxonomy/error_taxonomy.yaml`, git tag `taxonomy-v1.0`).

The taxonomy file defines the categories, the severity levels, and the
**classification rules** for choosing between categories. This file covers
everything else: the labeling procedure, judgment calls the taxonomy can't
settle, and severity tie-breakers. If the two ever disagree, the taxonomy wins;
fix this file.

## Setup
- Notes are **blinded**: you see a random note ID, never the prompt that wrote it.
  The key lives in `annotation/key_main.csv`. Do not open this until annotation is finished.
- Notes are shown in **random order**, so fatigue and learning effects spread evenly
  across prompts.
- The annotation tool shows each category's definition and each severity level's
  definition, but **not** the classification rules. Keep `taxonomy/error_taxonomy.yaml`
  open beside the tool, or print the rules, until you know them.

## Procedure for each note
1. Read the full transcript once without looking at the note.
2. Read the note top to bottom. For each statement, check it against the transcript.
   Log each unsupported, wrong, misattributed, mis-certain or misplaced statement as one error.
3. Re-scan the transcript for clinically relevant content missing from the note. Log each as an OMISSION.
4. For synthetic ED cases, mark each item on the trap checklist pass, fail, or na.
5. Give the note an overall quality rating (1 to 5): "How much editing before I would sign this?"
   5 = sign as is, 4 = trivial edits, 3 = several edits, 2 = major rewrite, 1 = unusable.
6. Mark the note reviewed. A reviewed note with zero errors is a real result: it means "no errors found."

## Choosing the category
Apply the classification rules in the taxonomy. In short:
- **One error per distinct fact.** A wrong fact repeated in two sections is logged once.
- **Most specific category wins.** HALLUCINATION is the fallback for unsupported content
  that fits nothing more specific.
- **A substituted value is one error.** "Metoprolol 25 mg" documented as "50 mg" is one
  NUMERIC_MED error, not an OMISSION plus a HALLUCINATION.
- **Timing goes to TEMPORAL**, even when it's a number (durations, onset, dates).
- **Excluded vs uncertain:** stated as absent or ruled out but documented as present is
  NEGATION; stated as possible, suspected, or under evaluation but documented as confirmed
  (or the reverse) is CERTAINTY.
- **Never mentioned vs wrong certainty:** a diagnosis never mentioned in the transcript is
  HALLUCINATION; a mentioned diagnosis documented with the wrong certainty is CERTAINTY.

## Judgment calls the taxonomy doesn't settle
- **Omission threshold.** Count it only if a clinician covering this patient would want it
  in the note, for the presenting problem, assessment, treatment, safety, or follow-up.
  Don't count small talk, repeated statements, or social pleasantries.
- **Paraphrase is fine.** "Denies SOB" for "I'm not short of breath at all" is correct.
- **Reasonable inference is not hallucination** only when it is trivially implied (e.g.,
  "58-year-old male" when the patient states his age and is referred to as he/him).
  An assessment or diagnosis the clinician never voiced is a HALLUCINATION, even if it is
  clinically reasonable.
- **Hedged clinician language.** "I'm worried about...", "I'm concerned this could be...",
  "I think you're...", "let's rule out..." all signal an uncertain diagnosis. A note that
  states the diagnosis as fact is a CERTAINTY error. Wording such as "suspected",
  "possible", "concern for", "likely", or "rule out" in the note preserves the uncertainty
  and is correct.
- **Transcript noise.** ACI-Bench transcripts contain speech-recognition-style errors. If the
  transcript is ambiguous, don't penalize a reasonable reading. Note the case in the
  decision log.
- **Correct note, wrong reference.** Grade against the transcript only. ACI-Bench reference
  notes are not shown and are not the standard.

## Severity: tie-breakers
Severity levels are **1 Minor, 2 Moderate, 3 Major**, defined in the taxonomy.
- If unsure between two levels, pick the **lower** one and add a comment. Consistency
  matters more than any single call.
- Anything touching **anticoagulants, allergies, insulin, opioids, laterality for a
  procedure, or a red-flag symptom** starts at severity 3 (Major) unless clearly harmless.
- A CERTAINTY error that turns a suspected **serious** diagnosis into a confirmed one, or
  turns a confirmed one into "possible" (e.g., sepsis, ACS, PE, GI bleed), starts at
  severity 3, because it can drive or withhold treatment and affects coding.
- Missing billing-relevant detail (e.g., a chronic condition addressed but not documented)
  is usually severity 2.

## Intra-rater reliability
Following your first pass at the annotations but before running the judge or looking at any results, re-label and re-annotate a random 15 notes. 
Separate the first and second passes by at least a day. Compare major errors and error categories.

## Log your judgment calls
Keep a running list of hard cases in `annotation/decision_log.md`. Each entry should be a
sentence or two: the situation and the rule you applied. If a hard case reveals a gap in
the taxonomy, don't change the taxonomy mid-annotation. Log it, apply the closest rule
consistently, and propose the fix as a limitation or next step.
