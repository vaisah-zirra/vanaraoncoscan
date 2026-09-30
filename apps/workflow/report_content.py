"""Versioned, authored responses for the workflow prototype; never clinical sign-off."""
RESPONSE_VERSION = 'specialist-response-1.1'
RESPONSES = {
    'SUSPICIOUS': [
        ('Review summary', 'The recorded assessment identifies a focal area requiring further specialist evaluation. The highlighted region provides a location for review; it does not establish the nature of the tissue or confirm malignancy.'),
        ('Clinical correlation', 'The presenting concern should be reconciled with the full breast examination and complete imaging study. Confirm that the area evaluated corresponds to the clinical concern. Laterality and location in the history are recorded clinical context, not verified image identifiers.'),
        ('Specialist impression', 'Suspicious assessment requiring further characterization. A definitive diagnosis, imaging category and lesion measurements cannot be assigned from this workflow record.'),
        ('Recommended evaluation', 'Proceed through the locally agreed breast assessment pathway. The receiving specialist should review the complete examination and determine whether additional imaging or tissue sampling is appropriate.'),
        ('Handover requirements', 'Provide the presenting history, relevant examination findings, prior imaging where available and the recorded referral question. Return the specialist findings and management recommendation to the referring facility.'),
    ],
    'NON_SUSPICIOUS': [
        ('Review summary', 'The recorded assessment follows a non-suspicious pathway within the limited scope of the selected image. This finding should be considered alongside the clinical concern rather than treated as a complete examination result.'),
        ('Clinical correlation', 'Confirm that the assessed area corresponds to the presenting symptom. No prior imaging comparison, physical examination result or complete acquisition series is supplied by the image library.'),
        ('Specialist impression', 'No escalation is established by the predefined image assessment alone. A non-suspicious result does not exclude every cause of a breast symptom or all breast disease.'),
        ('Recommended evaluation', 'The responsible clinician should document concordance between the history, examination and imaging, and record an appropriate follow-up plan. Persistent or changing symptoms require reassessment.'),
        ('Continuity of care', 'Record who will review the patient, the agreed review date and the reason for follow-up. If the clinical concern is not explained by the assessment, seek specialist input before closing the case.'),
    ],
    'UNCERTAIN': [
        ('Review summary', 'The available assessment remains indeterminate. The highlighted region is retained for specialist review, but the workflow does not provide sufficient information to select a definitive care pathway.'),
        ('Clinical correlation', 'Review the full acquisition and correlate it with the presenting concern. Confirm image orientation, target coverage and whether prior imaging is available. These details cannot be established from the selected frame alone.'),
        ('Specialist impression', 'Interpretive uncertainty remains unresolved. This predefined response is not a signed specialist conclusion and does not change the pending review status.'),
        ('Recommended evaluation', 'Request review of the complete examination and the specific clinical question. The specialist should determine whether further imaging, referral or follow-up is appropriate after reconciling the available information.'),
        ('Continuity of care', 'Keep the case open until the recommendation has been documented and acknowledged by the responsible clinician. A follow-up date or referral destination should only appear as confirmed when it has been recorded in the care plan.'),
    ],
    'QUALITY_FAILURE': [
        ('Review summary', 'Diagnostic interpretation is withheld because the recorded quality check did not pass. The specific technical limitation is documented in the image-quality section of this report.'),
        ('Specialist impression', 'No assessment disposition can be assigned from this submission. Image-quality failure must not be interpreted as a normal or reassuring finding.'),
        ('Recommended action', 'Obtain an appropriate replacement acquisition or source image addressing the stated limitation, and repeat the quality check before assessment. Preserve the presenting history and the previous quality record for continuity.'),
        ('Continuity of care', 'The responsible clinician should retain oversight of the presenting concern while an adequate examination is arranged. This report records the interrupted workflow and does not replace clinical evaluation.'),
    ],
}
RESPONSES['REVIEW_REQUIRED'] = RESPONSES['UNCERTAIN']
