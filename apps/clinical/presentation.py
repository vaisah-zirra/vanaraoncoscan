"""Shared display vocabulary and explicit illustrative scores, never model measurements."""
PRESENTATION_VERSION = 'assessment-display-1.0'
LEGEND = [
    {'key':'benign','label':'Benign-appearing finding','color':'#19765B','meaning':'Imaging features favour a benign finding. Clinical correlation is still required.'},
    {'key':'clear','label':'No suspicious finding identified','color':'#23788A','meaning':'No suspicious finding is identified in the analysed image. This does not exclude all breast disease.'},
    {'key':'indeterminate','label':'Indeterminate finding','color':'#9A650D','meaning':'The finding cannot be confidently characterized; further evaluation is required.'},
    {'key':'suspicious','label':'Suspicious for malignancy','color':'#B54D25','meaning':'A concerning finding warrants specialist evaluation. Cancer is not confirmed.'},
    {'key':'high','label':'Highly suggestive of malignancy','color':'#A8324A','meaning':'Imaging features are highly suggestive of malignancy and warrant urgent specialist evaluation; tissue diagnosis is required to confirm cancer.'},
    {'key':'unavailable','label':'Assessment withheld','color':'#677582','meaning':'No interpretation or confidence score is issued when image quality is insufficient.'},
]
BY_KEY = {item['key']:item for item in LEGEND}
# Scores illustrate confidence in the displayed classification, not cancer risk or accuracy.
SAMPLE_DISPLAYS = {
    'sample-01':('benign',91.3),
    'sample-02':('clear',96.4),
    'sample-03':('clear',94.8),
    'sample-04':('indeterminate',61.7),
    'sample-05':('high',93.6),
}


def assessment_display(case):
    assessment=getattr(case,'aiassessment',None)
    quality=getattr(case,'qualityassessment',None)
    attachment=getattr(case,'attachment',None)
    score=None
    if quality and not quality.adequate:
        key='unavailable'
    elif not assessment:
        return {'key':'pending','label':'Assessment pending','color':'#677582','meaning':'Complete image-quality review and assessment to obtain a result.',
            'score':None,'has_score':False,'remaining':100,'version':PRESENTATION_VERSION}
    else:
        key={'NON_SUSPICIOUS':'clear','SUSPICIOUS':'suspicious','UNCERTAIN':'indeterminate','REVIEW_REQUIRED':'indeterminate'}.get(assessment.disposition,'indeterminate')
        result=assessment.details or {}
        if (quality and quality.adequate and attachment and case.patient.is_synthetic and case.patient.facility.is_demo
            and result.get('sample_id') == attachment.sample_id and result.get('image_sha256') == attachment.sample.sha256):
            mapped=SAMPLE_DISPLAYS.get(attachment.sample.code)
            expected={'sample-01':'NON_SUSPICIOUS','sample-02':'NON_SUSPICIOUS','sample-03':'NON_SUSPICIOUS','sample-04':'UNCERTAIN','sample-05':'SUSPICIOUS'}
            if mapped and assessment.disposition == expected[attachment.sample.code]:
                key,score=mapped
    return {**BY_KEY[key], 'score':score, 'has_score':score is not None,'remaining':round(100-score,1) if score is not None else 100,'version':PRESENTATION_VERSION}
