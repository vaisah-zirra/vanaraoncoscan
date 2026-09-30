"""Authored case fixtures for workflow evaluation, not image-derived findings.

Keep prototype disclosure in the application shell and any exported report.
Clinical wording reference: https://www.radiologyinfo.org/en/info/breastus
These fixtures require specialist review before any clinical use.
"""
CASE_CONTENT = {
    'A': {
        'context': 'Reason for assessment: Intermittent discomfort in the upper outer left breast over the past three weeks.\nRelevant history: No reported nipple discharge, skin change or recent trauma.\nAssessment request: Targeted evaluation of the symptomatic area and correlation with the clinical examination.',
        'quality': 'Coverage: The area of concern is represented in two planes.\nImage quality: Tissue interfaces are adequately visualized, without a material acquisition limitation recorded.',
        'finding': 'Findings: No discrete focal abnormality is described in the assessed area.\nImpression: Non-suspicious assessment within the scope of the available study.\nNext step: Correlate with the clinical examination and document symptom review. Persistent or changing symptoms require reassessment; this result does not exclude all breast disease.',
        'followup': 'Review symptom progression and correlate with the clinical examination. Record any new palpable finding, nipple discharge or skin change, and whether further assessment is required.',
    },
    'B': {
        'context': 'Reason for assessment: Newly noticed palpable lump in the upper outer right breast, present for approximately two weeks.\nRelevant history: No reported recent breast trauma or previous assessment of this lump.\nAssessment request: Characterize the area of concern and determine the appropriate referral pathway.',
        'quality': 'Coverage: The palpable area is represented in orthogonal views.\nImage quality: The region of interest and adjacent tissue are adequately visualized for review.',
        'finding': 'Findings: A focal abnormality is described at the site of the palpable concern.\nImpression: Suspicious finding requiring specialist evaluation. This assessment does not establish a diagnosis of malignancy.\nNext step: Arrange breast-imaging review and correlation with the clinical examination. The responsible specialist should determine any additional imaging or tissue sampling required.',
        'referral': 'Indication: Palpable right breast lump with a suspicious assessment.\nRequested evaluation: Specialist breast assessment, review of the available study and correlation with examination findings.\nClinical question: Determine the need for additional imaging and image-guided tissue sampling.\nHandover: Return the specialist findings and management recommendation to the referring facility.',
    },
    'C': {
        'context': 'Reason for assessment: Focal thickening in the upper inner left breast, with intermittent tenderness.\nRelevant history: No previous study is available for comparison.\nAssessment request: Review the area of concern because the initial assessment does not provide a sufficiently clear disposition.',
        'quality': 'Coverage: The area of concern is included in two planes.\nImage quality: Acquisition is adequate for review; the limitation is uncertainty in interpretation rather than a failed quality check.',
        'finding': 'Findings: The available assessment does not confidently characterize the focal area of concern.\nImpression: Indeterminate assessment; a definitive disposition has not been assigned.\nNext step: Obtain specialist review of the study and clinical context before confirming the referral or follow-up pathway.',
    },
    'D': {
        'context': 'Reason for assessment: Localized right breast discomfort with a reported palpable area of concern.\nStudy limitation: The submitted acquisition does not fully demonstrate the target area.\nAssessment request: Obtain an adequate targeted study before proceeding with interpretation.',
        'quality': 'Coverage: The target area is incompletely visualized and an adequate orthogonal view is missing.\nImage quality: The available acquisition is insufficient for a reliable assessment.\nRequired action: Reacquire targeted views with appropriate coverage and repeat the quality check. No automated assessment has been generated.',
        'finding': '',
    },
}
