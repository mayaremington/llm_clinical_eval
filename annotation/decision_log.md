# Annotation Decision log

Log of tough annotation calls and interesting observations

### Psoriatic arthritis case
    Joint exam (part of PE) is very tricky - hard to separate patient reported pain vs tenderness elicited on exam (“tenderness” never mentioned explicitly, instead clinician uses term “pain”)
        Grounded - put joint “exam” in S
        Baseline - uses “tenderness” (hallucination) and puts it in physical exam (as well as in S)

### Migraine ED case
    Patient reports “zigzag lines” prior to headache onset
        Baseline concludes this is aura, grounded has no mention of aura
        Conclusion: both are acceptable, but I actually prefer baseline because conversion to medical terminology can be useful 
        Downstream result: affects PMH and diagnosis:
            Grounded: Migraine
            Baseline: Migraine with visual aura
	
### Chest pressure ED case
    Baseline converts pt symptoms and PE findings into medical terms
        Examples:
            S:  “sweating/sweaty” becomes diaphoresis
            O: During physical exam, “pressing on chest” becomes palpation

### CHF case
    Grounded is word-for-word the transcript
    Baseline summarizes findings in assessment section, adds medical terminology
        Distended neck veins → jugular venous distension
        Difficulty breathing lying down → orthopnea


### Stroke ED case
    Grounded
        CC is verbatim and unnecessarily attributed to patient: 
            Right arm and right leg not working properly (per patient)
    Baseline
        CC is in medical terminology, appropriately derived from text (preferable):
            Right arm and right leg weakness with slowed speech
        Did jump to conclusions - minor hallucination (not desirable):
            Can’t lift arm high → limited OVERHEAD rom

