"""Structured breast-ultrasound reports for the demo image library.

Descriptors follow the ACR BI-RADS® Atlas (5th edition) ultrasound lexicon and were
written by reading each library image; morphometrics are computed from the matching
BUS-UCLM segmentation mask. They are authored demo content, not model inference, and
require review by a breast radiologist before any clinical or marketing use.

Lexicon reference: ACR BI-RADS® Atlas, 5th ed., Ultrasound (Mendelson et al., 2013).
"""
REPORT_VERSION = 'structured-us-report-1.0'
MODEL_NAME = 'VOS-BUS'
MODEL_VERSION = '0.9.4'
MODEL_LABEL = f'{MODEL_NAME} v{MODEL_VERSION} (investigational)'

# Model confidence below this value routes the case to teleradiology review.
TELERADIOLOGY_THRESHOLD = 70

SIGNALS = {
    'benign': 'Favours benign',
    'suspicious': 'Suspicious feature',
    'neutral': 'Non-discriminating',
}

BIRADS = {
    '0': ('Incomplete', 'Not applicable', 'Additional imaging evaluation needed before a final category can be assigned.'),
    '1': ('Negative', 'Essentially 0%', 'Routine age-appropriate screening; manage any clinical concern on its own merits.'),
    '2': ('Benign', 'Essentially 0%', 'Routine age-appropriate screening.'),
    '3': ('Probably benign', '>0% to ≤2%', 'Short-interval (6-month) ultrasound follow-up, then surveillance for 2 years.'),
    '4A': ('Low suspicion for malignancy', '>2% to ≤10%', 'Tissue diagnosis (image-guided core biopsy).'),
    '4B': ('Moderate suspicion for malignancy', '>10% to ≤50%', 'Tissue diagnosis (image-guided core biopsy).'),
    '4C': ('High suspicion for malignancy', '>50% to <95%', 'Tissue diagnosis (image-guided core biopsy).'),
    '5': ('Highly suggestive of malignancy', '≥95%', 'Tissue diagnosis (image-guided core biopsy) and appropriate action.'),
}

_TECHNIQUE = ('Targeted grayscale (B-mode) breast ultrasound using a high-frequency linear-array transducer. '
              'A single representative static image was submitted for analysis. Colour/power Doppler, '
              'elastography and cine clips were not provided.')
_COMPARISON = 'No prior breast imaging available for comparison.'
_LOCATION_NOTE = ('Clock-face position, laterality and distance from the nipple are not encoded in the source image '
                  'and must be documented by the sonographer (refer to the body-marker pictogram).')


def _birads(code, provisional=False):
    name, likelihood, management = BIRADS[code]
    return {'category': code, 'name': name, 'likelihood': likelihood, 'management': management,
            'provisional': provisional}


REPORTS = {
    'sample-01': {
        'technique': _TECHNIQUE,
        'comparison': _COMPARISON,
        'composition': 'Heterogeneous background echotexture, with fibroglandular tissue interspersed with fat lobules.',
        'lesions': [{
            'label': 'Lesion 1',
            'type': 'Mass',
            'location': 'Superficial, in the anterior mammary zone immediately deep to the subcutaneous fat (upper ~7% of the imaged depth). ' + _LOCATION_NOTE,
            'descriptors': [
                ('Shape', 'Oval', 'benign', 'Elliptical outline; oval masses are most often benign.'),
                ('Orientation', 'Parallel (wider-than-tall)', 'benign', 'Long axis parallel to the skin line; width-to-height ratio 1.65 : 1.'),
                ('Margin', 'Circumscribed', 'benign', 'Well-defined, sharp interface with the surrounding tissue over essentially all of its circumference.'),
                ('Echo pattern', 'Hypoechoic, with fine low-level internal echoes', 'neutral', 'Echogenicity below that of fat. A thin linear internal echo is seen in the lower half of the mass.'),
                ('Posterior features', 'Mild posterior acoustic enhancement', 'benign', 'Increased through-transmission deep to the mass; no posterior shadowing.'),
                ('Calcifications', 'None identified', 'benign', 'No echogenic foci with shadowing within the mass.'),
                ('Associated features', 'None', 'benign', 'No architectural distortion, duct change, skin thickening or oedema.'),
            ],
        }],
        'morphometrics': {'width_px': 228, 'height_px': 138, 'aspect_ratio': 1.65, 'area_px': 25312,
                          'circularity': 0.89, 'solidity': 0.974, 'depth_top_pct': 7},
        'birads': _birads('3'),
        'impression': [
            'Solitary oval, parallel, circumscribed hypoechoic mass with mild posterior acoustic enhancement in the anterior mammary zone, most consistent with a fibroadenoma.',
            'No sonographic features of malignancy (no irregular shape, non-parallel orientation, non-circumscribed margin, posterior shadowing or architectural distortion).',
            'BI-RADS 3 – Probably benign.',
        ],
        'recommendations': [
            'Short-interval follow-up breast ultrasound in 6 months, then at 12 and 24 months to document stability.',
            'Correlate with clinical breast examination; document the clock-face position and distance from the nipple.',
            'Upgrade to tissue sampling (US-guided core biopsy) if the longest diameter increases by ≥20% within 6 months, if suspicious features develop, if the patient is at high risk, or if the patient prefers a definitive diagnosis.',
            'Consider colour Doppler at follow-up to assess internal vascularity and help exclude a complicated cyst.',
        ],
        'differential': [
            ('Fibroadenoma', 'Most likely', 'Classic oval, parallel, circumscribed hypoechoic solid-appearing mass.'),
            ('Complicated cyst', 'Possible', 'Low-level internal echoes with posterior enhancement can mimic a solid mass; Doppler would help separate the two.'),
            ('Phyllodes tumour', 'Less likely', 'Considered if the mass is large or grows rapidly at follow-up.'),
        ],
        'reasoning': ('Six of the seven BI-RADS lexicon descriptors fall in the benign-favouring group: the mass is oval, '
                      'parallel to the skin, circumscribed, shows posterior enhancement rather than shadowing and has no '
                      'calcifications or associated features. Shape analysis of the lesion outline agrees: high circularity '
                      '(0.89) and solidity (0.97) indicate a smooth, convex contour without angular or spiculated projections. '
                      'This combination places the lesion in the probably-benign category (malignancy likelihood ≤2%), for which '
                      'imaging surveillance is an accepted alternative to biopsy.'),
        'patient_summary': ('The scan shows a small, smooth, oval lump that sits flat in the breast tissue. Lumps with these features '
                            'are almost always harmless; the most common cause is a fibroadenoma, a benign growth of breast tissue. '
                            'Your clinician will usually recommend a repeat scan in 6 months to make sure it has not changed. '
                            'Please return earlier if the lump grows, becomes painful, or you notice skin or nipple changes.'),
        'specialist': [
            ('Concordance with AI', 'Agree. The AI segmentation accurately outlines the mass, the BI-RADS lexicon descriptors are concordant with my interpretation and BI-RADS 3 is appropriate.'),
            ('Specialist findings', 'Targeted grayscale breast ultrasound, single representative static image of the area of clinical concern. Background echotexture is heterogeneous. In the anterior mammary zone, immediately deep to the subcutaneous fat, there is a solitary oval mass with its long axis parallel to the skin. Margins are circumscribed throughout. The mass is hypoechoic relative to fat, with fine low-level internal echoes and a thin linear internal echo, and shows mild posterior acoustic enhancement. There is no internal calcification, no surrounding architectural distortion, no duct dilatation and no skin thickening. Size in millimetres, internal vascularity and the axilla cannot be assessed from the submitted image.'),
            ('Specialist impression', 'BI-RADS 3 – Probably benign.\nSolitary oval, parallel, circumscribed hypoechoic mass, most in keeping with a fibroadenoma. A complicated cyst is the main alternative. No suspicious sonographic features.'),
            ('Recommendation', '1. Short-interval follow-up breast ultrasound in 6 months, then at 12 and 24 months to confirm stability.\n2. Proceed to ultrasound-guided core biopsy instead of surveillance if the longest diameter increases by ≥20% within 6 months, if suspicious features develop, if the patient is at high risk (strong family history, known BRCA mutation, prior chest irradiation), or if she prefers a tissue diagnosis.\n3. Add colour Doppler at the follow-up scan to assess internal vascularity and exclude a complicated cyst.\n4. Correlate with clinical breast examination to confirm the mass corresponds to the palpable concern.'),
            ('Handover', 'At follow-up, record laterality, clock-face position, distance from the nipple and three orthogonal measurements in millimetres to allow accurate comparison. Advise the patient to return sooner if the lump enlarges or new symptoms develop.'),
        ],
    },
    'sample-02': {
        'technique': _TECHNIQUE,
        'comparison': _COMPARISON,
        'composition': 'Homogeneous background echotexture – fat, with lobulated subcutaneous and mammary fat separated by echogenic Cooper ligaments.',
        'lesions': [],
        'normal_findings': [
            'Skin and subcutaneous tissue are of normal thickness and echogenicity.',
            'Normal fat lobules with intact, thin echogenic Cooper ligaments.',
            'No solid or cystic mass, no architectural distortion and no ductal dilatation.',
            'No abnormal posterior acoustic shadowing.',
        ],
        'morphometrics': None,
        'birads': _birads('1'),
        'impression': [
            'Normal breast ultrasound appearance in the imaged field.',
            'No sonographic evidence of a mass, cyst or architectural distortion.',
            'BI-RADS 1 – Negative.',
        ],
        'recommendations': [
            'No additional imaging is required on the basis of this image.',
            'Continue routine, age-appropriate breast screening.',
            'A palpable or persistent clinical abnormality must not be dismissed on imaging alone; consider specialist clinical review or further imaging if the concern remains.',
        ],
        'differential': [],
        'reasoning': ('The model detected no focal region with mass characteristics. Tissue planes are preserved, Cooper ligaments '
                      'are intact and continuous, and there is no area of abnormal echogenicity or posterior shadowing. '
                      'No lesion was segmented, so no bounding box was drawn.'),
        'patient_summary': ('The scan of this area of your breast looks normal. No lump, cyst or other abnormal area was seen. '
                            'Keep up with your usual breast checks and screening, and see your clinician if you notice any new '
                            'lump, skin change or nipple discharge, or if a symptom does not go away.'),
        'specialist': [
            ('Concordance with AI', 'Agree. No focal abnormality is present and the AI correctly did not mark a region of interest.'),
            ('Specialist findings', 'Targeted grayscale breast ultrasound, single representative static image of the area of clinical concern. Background echotexture is homogeneous – fat. Skin and subcutaneous tissue are of normal thickness and echogenicity. Fat lobules are separated by thin, intact echogenic Cooper ligaments with a normal course. There is no solid or cystic mass, no architectural distortion, no ductal dilatation and no area of abnormal posterior acoustic shadowing. The retromammary region is unremarkable within the field of view.'),
            ('Specialist impression', 'BI-RADS 1 – Negative.\nNormal breast ultrasound appearance in the imaged region.'),
            ('Recommendation', '1. No further imaging is required on the basis of this study.\n2. Continue routine, age-appropriate breast screening.\n3. If a palpable abnormality persists, confirm that the scanned area corresponds to the site of concern. A clinically suspicious lump warrants specialist clinical assessment even when ultrasound is negative.'),
            ('Handover', 'Safety-netting: advise the patient to return if she notices a new lump, skin dimpling or thickening, nipple inversion or nipple discharge.'),
        ],
    },
    'sample-03': {
        'technique': _TECHNIQUE,
        'comparison': _COMPARISON,
        'composition': 'Homogeneous background echotexture – fibroglandular, with interspersed fat lobules.',
        'lesions': [],
        'normal_findings': [
            'Skin, subcutaneous fat and retromammary space are unremarkable; the pectoral fascia is intact.',
            'A small ill-defined hypoechoic area in the left mid-field has the appearance of a normal fat lobule/tissue interface, with no space-occupying effect or posterior features.',
            'No solid or cystic mass and no architectural distortion.',
        ],
        'morphometrics': None,
        'birads': _birads('1'),
        'impression': [
            'Normal breast ultrasound appearance in the imaged field.',
            'Focal hypoechoic area in the mid-field is in keeping with normal fat lobule (pseudo-lesion) and does not meet criteria for a mass.',
            'BI-RADS 1 – Negative.',
        ],
        'recommendations': [
            'No additional imaging is required on the basis of this image.',
            'Continue routine, age-appropriate breast screening.',
            'If the hypoechoic area corresponds to a palpable abnormality, rescan it in an orthogonal plane to confirm it elongates and blends with surrounding fat.',
        ],
        'differential': [],
        'reasoning': ('No region met the model\'s criteria for a mass. A small hypoechoic area was evaluated and classified as a '
                      'normal fat lobule because it lacks a defined margin, has no mass effect on adjacent Cooper ligaments and '
                      'shows no posterior shadowing or enhancement. No lesion was segmented, so no bounding box was drawn.'),
        'patient_summary': ('The scan of this area of your breast looks normal. A small darker patch on the image is normal fatty '
                            'tissue, not a lump. Keep up with your usual screening and see your clinician if you notice any new or '
                            'persistent change.'),
        'specialist': [
            ('Concordance with AI', 'Agree. The hypoechoic area in the mid-field is a normal fat lobule and the AI correctly did not classify it as a mass.'),
            ('Specialist findings', 'Targeted grayscale breast ultrasound, single representative static image of the area of clinical concern. Background echotexture is homogeneous – fibroglandular, with interspersed fat lobules. Skin, subcutaneous fat and pectoral fascia are normal. A small, ill-defined hypoechoic area in the mid-field blends with the surrounding fat, has no mass effect on adjacent Cooper ligaments and no posterior features, in keeping with a normal fat lobule (pseudo-lesion). There is no solid or cystic mass and no architectural distortion.'),
            ('Specialist impression', 'BI-RADS 1 – Negative.\nNormal study; the mid-field hypoechoic area represents a normal fat lobule.'),
            ('Recommendation', '1. No further imaging is required on the basis of this study.\n2. Continue routine, age-appropriate breast screening.\n3. If the hypoechoic area coincides with a palpable concern, scan it in the orthogonal plane: a fat lobule will elongate and merge with the adjacent fat, whereas a true mass remains discrete.'),
            ('Handover', 'Safety-netting: advise the patient to return if she notices a new or changing lump, skin change or nipple discharge.'),
        ],
    },
    'sample-04': {
        'technique': _TECHNIQUE,
        'comparison': _COMPARISON,
        'composition': 'Heterogeneous background echotexture, with prominent subcutaneous fat lobules overlying fibroglandular tissue.',
        'lesions': [{
            'label': 'Lesion 1',
            'type': 'Possible mass vs. prominent fat lobule',
            'location': 'Subcutaneous/premammary layer, superficial (upper ~10% of the imaged depth). ' + _LOCATION_NOTE,
            'descriptors': [
                ('Shape', 'Oval', 'benign', 'Smooth elliptical outline.'),
                ('Orientation', 'Parallel (wider-than-tall)', 'benign', 'Width-to-height ratio 1.61 : 1.'),
                ('Margin', 'Circumscribed, with a thin echogenic rim', 'benign', 'Sharp interface; a thin echogenic capsule-like rim is seen superiorly and inferiorly.'),
                ('Echo pattern', 'Isoechoic (relative to subcutaneous fat)', 'neutral', 'Echogenicity is close to that of adjacent fat lobules, which limits separation of a true mass from normal fat.'),
                ('Posterior features', 'No posterior features', 'neutral', 'Neither enhancement nor shadowing; this does not help distinguish cystic from solid content.'),
                ('Calcifications', 'None identified', 'benign', 'No echogenic foci.'),
                ('Associated features', 'None', 'benign', 'No architectural distortion, skin thickening or oedema.'),
            ],
        }],
        'morphometrics': {'width_px': 171, 'height_px': 106, 'aspect_ratio': 1.61, 'area_px': 13726,
                          'circularity': 0.91, 'solidity': 0.991, 'depth_top_pct': 10},
        'birads': _birads('0', provisional=True),
        'impression': [
            'Oval, parallel, circumscribed lesion in the subcutaneous layer that is near-isoechoic to surrounding fat.',
            'On a single plane it is not possible to determine whether this is a true mass (lipoma, fibroadenoma, intramammary lymph node) or a prominent fat lobule (pseudo-lesion).',
            'AI confidence 61.7% is below the 70% teleradiology threshold. Final category withheld pending specialist review; provisional range BI-RADS 2–3.',
        ],
        'recommendations': [
            'Teleradiologist review of this image (automatically requested).',
            'Rescan in the orthogonal plane: a fat lobule will elongate and merge with adjacent fat, whereas a true mass will remain discrete and oval in both planes.',
            'Apply colour Doppler (look for a fatty hilum with hilar flow to suggest an intramammary lymph node) and gentle compression (lipomas are typically soft and compressible).',
            'Assign a final BI-RADS category after review; do not discharge or close the case before then.',
        ],
        'differential': [
            ('Prominent fat lobule (pseudo-lesion)', 'Possible', 'Near-isoechoic to fat and located within the subcutaneous fat layer.'),
            ('Lipoma', 'Possible', 'Encapsulated, oval, near-isoechoic lesion in the subcutaneous fat.'),
            ('Fibroadenoma', 'Possible', 'Oval, parallel, circumscribed; less typical in this superficial location.'),
            ('Intramammary lymph node', 'Less likely', 'No echogenic fatty hilum is visible in this plane.'),
        ],
        'reasoning': ('The shape, orientation, margin and lack of associated features all favour a benign process, and contour analysis '
                      'shows a very smooth outline (solidity 0.99). However, the deciding feature, its echogenicity, is almost the same '
                      'as the surrounding fat, and there are no posterior features. With only one plane available, the model cannot '
                      'separate a true mass from normal fat. Its confidence (61.7%) is therefore below the 70% threshold, and the case was '
                      'routed to a teleradiologist rather than assigned a final category automatically.'),
        'patient_summary': ('The scan shows a small, smooth, oval area just under the skin. It does not have worrying features, but on '
                            'this single picture it is hard to tell whether it is normal fatty tissue or a small harmless lump such as a '
                            'lipoma. A breast imaging specialist has been asked to review it, and you may need one more quick scan from a '
                            'different angle. Your case stays open until that review is complete.'),
        'patient_summary_reviewed': ('A breast imaging specialist has reviewed your scan. The small, smooth area just under the skin '
                                     'is most likely a lipoma, a harmless fatty lump, or simply normal fatty tissue. To be sure, you '
                                     'will be offered one more short scan from a different angle. If it confirms a lipoma or normal '
                                     'tissue, no further tests are needed; otherwise a check-up scan in 6 months is usually advised. '
                                     'Please come back sooner if the lump grows, becomes painful, or you notice skin changes.'),
        'specialist': [
            ('Concordance with AI', 'Partially agree. The AI descriptors are accurate and its low confidence was appropriate for a single plane. On specialist review, the thin echogenic capsule and isoechogenicity to subcutaneous fat favour a benign fat-containing lesion, so I have assigned a final category.'),
            ('Specialist findings', 'Targeted grayscale breast ultrasound, single representative static image of the area of clinical concern. Background echotexture is heterogeneous, with prominent subcutaneous fat lobules. Within the subcutaneous (premammary) layer there is an oval, parallel, circumscribed lesion with a thin echogenic capsule. It is isoechoic to the surrounding subcutaneous fat, with fine internal echogenic striations parallel to the skin. There are no posterior acoustic features, no calcification, no architectural distortion and no skin thickening. No echogenic fatty hilum is demonstrated to suggest an intramammary lymph node.'),
            ('Specialist impression', 'BI-RADS 3 – Probably benign.\nSubcutaneous lesion most in keeping with a lipoma; a prominent fat lobule (pseudo-lesion) is the main alternative. Fibroadenoma is less likely given the subcutaneous location. No suspicious features.'),
            ('Recommendation', '1. Targeted repeat ultrasound at the facility with orthogonal views, gentle compression and colour Doppler.\n2. If confirmed as a lipoma (soft, compressible, avascular) or a fat lobule (elongates and merges with fat in the orthogonal plane), downgrade to BI-RADS 2 and return to routine care.\n3. If it remains a discrete solid mass in both planes, continue BI-RADS 3 management with follow-up ultrasound at 6 months.\n4. Image-guided core biopsy only if the lesion enlarges or develops suspicious features.'),
            ('Handover', 'Send the repeat-scan images through the same teleradiology pathway for comparison, with clock-face position and distance from the nipple recorded.'),
        ],
    },
    'sample-05': {
        'technique': _TECHNIQUE,
        'comparison': _COMPARISON,
        'composition': 'Heterogeneous background echotexture.',
        'lesions': [{
            'label': 'Lesion 1',
            'type': 'Mass',
            'location': 'Mid mammary zone, within the fibroglandular layer (upper edge at ~22% of the imaged depth). ' + _LOCATION_NOTE,
            'descriptors': [
                ('Shape', 'Irregular', 'suspicious', 'Neither round nor oval; lobulated contour with angular projections.'),
                ('Orientation', 'Parallel, but near-round (width-to-height 1.23 : 1)', 'neutral', 'Only marginally wider than tall; a near-round configuration gives little of the reassurance of a clearly parallel mass.'),
                ('Margin', 'Not circumscribed – indistinct (echogenic halo) and angular', 'suspicious', 'Poorly defined interface with a thick echogenic halo, and angular margins at the superior and lateral edges.'),
                ('Echo pattern', 'Heterogeneous, predominantly hypoechoic', 'suspicious', 'Mixed internal echogenicity with darker central components.'),
                ('Posterior features', 'Posterior acoustic shadowing', 'suspicious', 'Column of reduced echoes deep to the mass, consistent with desmoplastic stromal reaction.'),
                ('Calcifications', 'None definitely identified', 'neutral', 'No discrete echogenic foci resolved on this image.'),
                ('Associated features', 'Architectural distortion', 'suspicious', 'Disruption and straightening of adjacent Cooper ligaments and tissue planes around the mass.'),
            ],
        }],
        'morphometrics': {'width_px': 134, 'height_px': 109, 'aspect_ratio': 1.23, 'area_px': 11388,
                          'circularity': 0.85, 'solidity': 0.955, 'depth_top_pct': 22},
        'birads': _birads('5'),
        'impression': [
            'Irregular, non-circumscribed (indistinct with echogenic halo, and angular), heterogeneous hypoechoic mass with posterior acoustic shadowing and surrounding architectural distortion.',
            'Appearances are highly suggestive of a primary breast carcinoma (most likely invasive ductal carcinoma of no special type).',
            'BI-RADS 5 – Highly suggestive of malignancy.',
        ],
        'recommendations': [
            'Urgent referral to a specialist breast unit (suspected cancer pathway; target first appointment within 2 weeks).',
            'Ultrasound-guided core needle biopsy (14G, minimum 3 cores) with marker-clip placement; send for histology and receptor status (ER, PR, HER2) and Ki-67.',
            'Targeted ultrasound of the ipsilateral axilla; FNA or core biopsy of any morphologically abnormal lymph node.',
            'Bilateral diagnostic mammography (with tomosynthesis if available) to assess extent and exclude multifocal, multicentric or contralateral disease.',
            'Discuss at the breast multidisciplinary team (MDT) meeting once histology is available; document radiology–pathology concordance.',
        ],
        'differential': [
            ('Invasive carcinoma of no special type (ductal)', 'Most likely', 'Irregular, indistinct, shadowing mass with echogenic halo – the classic sonographic pattern.'),
            ('Invasive lobular carcinoma', 'Possible', 'Can show posterior shadowing and architectural distortion with ill-defined margins.'),
            ('Radial scar / complex sclerosing lesion', 'Less likely', 'Can mimic distortion and shadowing; requires histology to exclude.'),
            ('Fat necrosis / post-traumatic change', 'Less likely', 'Consider only with a history of trauma or surgery; histology still required.'),
        ],
        'reasoning': ('Five of the seven BI-RADS lexicon descriptors are suspicious: irregular shape, a non-circumscribed '
                      '(indistinct, angular) margin with echogenic halo, heterogeneous hypoechoic echo pattern, posterior acoustic '
                      'shadowing and architectural distortion. None favours a benign process; although the mass is technically '
                      'parallel, it is nearly round. Angular and indistinct margins, the echogenic halo and shadowing each carry '
                      'a high positive predictive value for malignancy on their own. Contour analysis agrees: the lesion has the '
                      'lowest circularity (0.85), solidity (0.96) and width-to-height ratio (1.23) of the library masses. Because '
                      'management is driven by the most suspicious feature present, the overall category is BI-RADS 5.'),
        'patient_summary': ('The scan shows a lump with an irregular outline and other features that are a concern. This does not '
                            'confirm cancer – only a biopsy can do that – but it does mean you should be seen quickly by a breast '
                            'specialist. They will usually take a small tissue sample with a needle under local anaesthetic, using '
                            'ultrasound to guide it. Your clinician will arrange this referral with you. Please bring any previous '
                            'breast scans or reports to the appointment.'),
        'specialist': [
            ('Concordance with AI', 'Agree. The AI segmentation, lexicon descriptors and BI-RADS 5 category are concordant with my interpretation.'),
            ('Specialist findings', 'Targeted grayscale breast ultrasound, single representative static image of the area of clinical concern. Background echotexture is heterogeneous. In the mid mammary zone, within the fibroglandular layer, there is an irregular hypoechoic mass that is nearly round in configuration (width-to-height approximately 1.2 : 1). Margins are not circumscribed: indistinct with a thick echogenic halo, and angular at the superior and lateral aspects. The internal echo pattern is heterogeneous. There is posterior acoustic shadowing and architectural distortion of the adjacent Cooper ligaments. No discrete calcifications are resolved. The axilla is not included in the submitted image.'),
            ('Specialist impression', 'BI-RADS 5 – Highly suggestive of malignancy.\nIrregular, non-circumscribed, shadowing hypoechoic mass with echogenic halo and architectural distortion, in keeping with a primary breast carcinoma, most likely invasive carcinoma of no special type.'),
            ('Recommendation', '1. Urgent referral on the suspected breast cancer pathway (specialist breast clinic appointment within 2 weeks).\n2. Ultrasound-guided 14G core needle biopsy, minimum 3 cores, with marker-clip placement; request histological type and grade, ER, PR, HER2 and Ki-67.\n3. Targeted ipsilateral axillary ultrasound, with FNA or core biopsy of any morphologically abnormal lymph node.\n4. Bilateral diagnostic mammography (with tomosynthesis if available) to assess disease extent and exclude multifocal, multicentric or contralateral disease.\n5. Present at the breast multidisciplinary team meeting with histology; document radiology–pathology concordance. Staging and treatment planning as directed by the MDT.'),
            ('Handover', 'Urgent finding: please confirm receipt, and that the patient has been informed and referred. Record three-plane measurements in millimetres, clock-face position and distance from the nipple at the biopsy appointment.'),
        ],
    },
}


def morphometric_rows(m):
    """Readable morphometrics with a clinical gloss; inputs come from the segmentation mask."""
    if not m:
        return []
    ar = m['aspect_ratio']
    return [
        ('Width × height', f"{m['width_px']} × {m['height_px']} px",
         'Pixel spacing is not stored with the source image; millimetre size requires calibrated DICOM data.'),
        ('Width-to-height ratio', f'{ar:.2f} : 1',
         'Wider-than-tall (parallel), a benign-favouring feature.' if ar >= 1.4 else
         'Only slightly wider than tall; a near-round lesion gives little of the reassurance of a clearly parallel orientation.'),
        ('Circularity', f"{m['circularity']:.2f}",
         '1.00 is a perfect circle; lower values reflect lobulated or angular contours.'),
        ('Solidity (convexity)', f"{m['solidity']:.3f}",
         'Area divided by convex-hull area; values near 1.00 indicate a smooth convex outline without indentations or projections.'),
        ('Lesion area', f"{m['area_px']:,} px²", 'Segmented area on this image plane.'),
        ('Depth of upper margin', f"{m['depth_top_pct']}% of field depth", 'Relative position below the skin line.'),
    ]


def report_for_code(code):
    report = REPORTS.get(code)
    if not report:
        return None
    lesions = []
    for lesion in report['lesions']:
        descriptors = [{'feature': f, 'finding': v, 'signal': s, 'signal_label': SIGNALS[s], 'note': n}
                       for f, v, s, n in lesion['descriptors']]
        counts = {key: sum(1 for d in descriptors if d['signal'] == key) for key in SIGNALS}
        lesions.append({**lesion, 'descriptors': descriptors, 'counts': counts})
    return {**report, 'lesions': lesions, 'morphometric_rows': morphometric_rows(report['morphometrics']),
            'version': REPORT_VERSION, 'threshold': TELERADIOLOGY_THRESHOLD, 'model': MODEL_LABEL}


def report_for_assessment(assessment, attachment=None):
    """Return the structured report for an assessment whose snapshot matches its source sample."""
    if not assessment or not assessment.details:
        return None
    details = assessment.details
    code = details.get('sample_code')
    if not code and attachment and details.get('sample_id') == attachment.sample_id:
        code = attachment.sample.code
    if not code and details.get('sample_id'):
        from apps.clinical.models import UltrasoundSample
        code = UltrasoundSample.objects.filter(pk=details['sample_id']).values_list('code', flat=True).first()
    return report_for_code(code) if code else None
