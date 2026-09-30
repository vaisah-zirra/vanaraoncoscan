"""Private, on-demand PDF report. Export never signs a review or changes a case."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import json

import reportlab
from PIL import Image as PILImage
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, KeepTogether

from apps.clinical.models import AIAssessment, QualityAssessment
from apps.workflow.models import Referral
from apps.workflow.specialist_content import specialist_content
from apps.workflow.report_content import RESPONSES, RESPONSE_VERSION

from apps.clinical.presentation import assessment_display, LEGEND
from apps.workflow.confidence_pdf import ConfidenceCard

REPORT_VERSION = '1.7'
NOTICE = 'Workflow prototype · Not for clinical diagnosis'
INK = colors.HexColor('#183d3d')
TEAL = colors.HexColor('#147c70')
MUTED = colors.HexColor('#607b77')
PALE = colors.HexColor('#eff6f3')
LINE = colors.HexColor('#dce8e2')
FONT_DIR = Path(reportlab.__file__).parent/'fonts'
pdfmetrics.registerFont(TTFont('Report', str(FONT_DIR/'Vera.ttf')))
pdfmetrics.registerFont(TTFont('Report-Bold', str(FONT_DIR/'VeraBd.ttf')))
pdfmetrics.registerFontFamily('Report', normal='Report', bold='Report-Bold')


def stamp(value):
    return timezone.localtime(value).strftime('%d %b %Y, %H:%M %Z') if value else 'Not recorded'


def person(user):
    return (user.get_full_name() or user.username) if user else 'Not recorded'


def report_data(case):
    quality = QualityAssessment.objects.filter(case=case).first()
    assessment = AIAssessment.objects.filter(case=case).first()
    quality_failed = bool(quality and not quality.adequate)
    outcome = 'QUALITY_FAILURE' if quality_failed else assessment.disposition if assessment else 'PENDING'
    attachment = getattr(case, 'attachment', None)
    sample = attachment.sample if attachment else None
    specialist = specialist_content(case)
    reviews, signed, response = specialist['reviews'], specialist['signed'], specialist['response']
    # Failed quality takes precedence over any inconsistent legacy assessment.
    result = assessment.details if assessment and not quality_failed else {}
    referral = Referral.objects.filter(case=case).select_related('confirmed_by').first()
    followups = list(case.followup_set.order_by('due_date','pk'))
    decisions = list(case.clinical_decisions.select_related('actor').order_by('created_at','pk'))
    events = list(case.caseevent_set.select_related('actor').order_by('created_at','pk'))
    data = {
        'case':case, 'quality':quality, 'assessment':assessment if not quality_failed else None,
        'outcome':outcome, 'result':result, 'sample':sample, 'signed':signed, 'reviews':reviews,
        'response':response, 'referral':referral, 'followups':followups, 'decisions':decisions, 'events':events,
        'display':assessment_display(case), 'generated_at':timezone.now(), 'image_bytes':None, 'image_note':'No image is attached to this case.', 'boxes':[],
    }
    if sample:
        try:
            with sample.image.open('rb') as handle:
                raw = handle.read(10*1024*1024+1)
            if len(raw) > 10*1024*1024 or sha256(raw).hexdigest() != sample.sha256:
                raise ValueError('Image integrity mismatch')
            with PILImage.open(BytesIO(raw)) as image:
                if image.size != (sample.width, sample.height):
                    raise ValueError('Image dimensions changed')
                image.verify()
            data['image_bytes'] = raw
            data['image_note'] = 'Original source pixels retained. The image illustrates the selected prototype case; it is not an image of the named patient.'
            if result.get('sample_id') == sample.pk and result.get('image_sha256') == sample.sha256:
                data['boxes'] = [b for b in result.get('boxes',[]) if all(isinstance(b.get(k), (int,float)) for k in ('x','y','width','height')) and b['x'] >= 0 and b['y'] >= 0 and b['width'] > 0 and b['height'] > 0 and b['x']+b['width'] <= sample.width and b['y']+b['height'] <= sample.height]
            elif result:
                data['image_note'] += ' Assessment annotations are unavailable because the stored image reference does not match.'
        except (OSError, ValueError, PILImage.DecompressionBombError):
            data['image_note'] = 'Image unavailable for export: the file is missing, unreadable or no longer matches its stored integrity record. No replacement image or annotation has been supplied.'
    snapshot = {
        'display':data['display'], 'template':REPORT_VERSION, 'response_version':RESPONSE_VERSION, 'case':str(case.pk), 'status':case.status,
        'patient':[case.patient.reference,case.patient.display_name,case.patient.facility.name],
        'history':case.presenting_concern, 'quality': [quality.adequate,quality.reason,quality.details] if quality else None,
        'assessment':[assessment.disposition,assessment.finding,result] if assessment and not quality_failed else None,
        'image':[sample.sha256 if sample else None,data['image_note']], 'response':response,
        'reviews':[[r.pk,r.assessment,r.recommendation,person(r.reviewer),str(r.signed_at)] for r in reviews],
        'decisions':[[d.pk,d.action,d.notes,d.details,person(d.actor),str(d.created_at)] for d in decisions],
        'referral':[referral.destination,referral.reason,referral.urgency,person(referral.confirmed_by),str(referral.confirmed_at),referral.status,str(referral.appointment_date),[[u.status,u.notes,str(u.appointment_date),person(u.actor),str(u.created_at)] for u in referral.updates.select_related('actor').order_by('created_at','pk')]] if referral else None,
        'followups':[[f.pk,str(f.due_date),f.notes,str(f.completed_at),f.outcome,person(f.completed_by)] for f in followups],
        'events':[[e.pk,e.kind,str(e.created_at),person(e.actor)] for e in events],
    }
    data['revision'] = sha256(json.dumps(snapshot,sort_keys=True,default=str).encode()).hexdigest()[:12].upper()
    return data


class ImageComparison(Flowable):
    def __init__(self, data, width):
        super().__init__()
        self.data, self.width = data, width
        self.height = 205

    def draw(self):
        c = self.canv
        sample = self.data['sample']
        cell = (self.width-14)/2
        for index, label in enumerate(('ORIGINAL IMAGE', 'ANNOTATED VIEW')):
            x = index*(cell+14)
            c.setFillColor(INK); c.roundRect(x,0,cell,self.height,8,fill=1,stroke=0)
            c.setFillColor(colors.white); c.setFont('Report-Bold',8); c.drawString(x+12,self.height-20,label)
            scale = min((cell-16)/sample.width,(self.height-46)/sample.height)
            iw, ih = sample.width*scale, sample.height*scale
            ox, oy = x+(cell-iw)/2, (self.height-34-ih)/2
            c.drawImage(ImageReader(BytesIO(self.data['image_bytes'])),ox,oy,iw,ih)
            if index:
                c.setStrokeColor(colors.HexColor('#65e1b5')); c.setLineWidth(1.5)
                for box in self.data['boxes']:
                    c.rect(ox+box['x']*scale,oy+(sample.height-box['y']-box['height'])*scale,box['width']*scale,box['height']*scale,fill=0,stroke=1)


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, report_meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.states=[]
        self.meta=report_meta

    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total=len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.setFillColor(TEAL); self.setFont('Report-Bold',13)
            # Display the approved artwork directly; clip away the presentation sheet.
            logo = Path(__file__).resolve().parents[2] / 'static/brand/approved-brand-sheet.png'
            scale = 160 / 1125
            left, bottom = 42, A4[1]-52
            self.saveState()
            clip = self.beginPath(); clip.rect(left, bottom, 160, 300*scale)
            self.clipPath(clip, stroke=0, fill=0)
            self.drawImage(str(logo), left-90*scale, bottom+(190+300-1254)*scale, width=1254*scale, height=1254*scale)
            self.restoreState()
            self.setFillColor(MUTED); self.setFont('Report',7)
            self.drawRightString(A4[0]-42,A4[1]-32,'BREAST ULTRASOUND | CASE REPORT')
            self.drawRightString(A4[0]-42,A4[1]-44,self.meta['reference'])
            self.setStrokeColor(LINE); self.line(42,A4[1]-55,A4[0]-42,A4[1]-55)
            self.line(42,50,A4[0]-42,50)
            self.setFillColor(TEAL); self.setFont('Report-Bold',7)
            self.drawString(42,37,NOTICE)
            self.setFillColor(MUTED); self.setFont('Report',6.5)
            self.drawString(42,25,'Template '+REPORT_VERSION+' | Revision '+self.meta['revision'])
            self.drawRightString(A4[0]-42,25,f'Page {self._pageNumber} of {total}')
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def render_report(data):
    output=BytesIO()
    width=A4[0]-84
    styles={
        'title':ParagraphStyle('title',fontName='Report-Bold',fontSize=23,leading=29,textColor=INK,spaceAfter=14),
        'h':ParagraphStyle('h',fontName='Report-Bold',fontSize=13,leading=18,textColor=INK,spaceBefore=15,spaceAfter=9,keepWithNext=True),
        'label':ParagraphStyle('label',fontName='Report-Bold',fontSize=8,leading=11,textColor=TEAL,spaceAfter=4,keepWithNext=True),
        'body':ParagraphStyle('body',fontName='Report',fontSize=9,leading=14,textColor=INK,spaceAfter=9,splitLongWords=True),
        'small':ParagraphStyle('small',fontName='Report',fontSize=7.5,leading=11,textColor=MUTED,spaceAfter=6),
    }
    styles['response'] = ParagraphStyle('response', parent=styles['body'], leading=13, spaceAfter=6)
    def p(text, style='body'):
        return Paragraph(escape(str(text or 'Not recorded')).replace('\n','<br/>'),styles[style])
    story=[]
    def heading(text): story.append(p(text,'h'))
    def field(label,text): story.extend([p(label.upper(),'label'),p(text)])
    def table(rows,widths=None,compact=False):
        obj=Table([[p(cell,'small') for cell in row] for row in rows],colWidths=widths or [width/len(rows[0])]*len(rows[0]),hAlign='LEFT')
        obj.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.5,LINE),('INNERGRID',(0,0),(-1,-1),.3,LINE),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        if compact:
            obj.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        story.append(obj)
    case=data['case']; quality=data['quality']; assessment=data['assessment']; result=data['result']; sample=data['sample']
    cover=Table([[[p('ASSESSMENT & CONTINUITY OF CARE','label'),p('Breast ultrasound\nCase report','title'),p('IMAGING  /  REVIEW  /  CARE PLAN','small')],ConfidenceCard(data['display'],202)]],colWidths=[width-214,214])
    cover.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),15)]))
    story.append(cover)
    table([['PATIENT\n'+case.patient.display_name,'PATIENT REFERENCE\n'+case.patient.reference],['FACILITY\n'+case.patient.facility.name,'WORKFLOW STATUS\n'+case.get_status_display()],['CASE REFERENCE\n'+str(case.pk),'REPORT GENERATED\n'+stamp(data['generated_at'])]])
    story.append(Spacer(1,12))
    story.append(p('This report combines the recorded case information with a clearly identified predefined specialist response. It is an evaluation document, not a signed diagnostic report.','small'))
    heading('01  Clinical context')
    field('Presenting history & assessment request',case.presenting_concern)
    field('Examination scope','Selected breast ultrasound image and recorded workflow data. Complete acquisition series, examination findings, prior comparisons, age and date of birth are not recorded in this case model.')
    heading('02  Assessment overview')
    field('Assessment impression',data['display']['label'] if data['outcome']!='PENDING' else 'Assessment not yet completed.')
    story.append(p(data['display']['meaning'],'small'))
    field('Impression',result.get('impression') or (assessment.finding if assessment else 'No diagnostic interpretation is included.'))
    story.append(PageBreak())
    story.append(p('Image review & findings','title'))
    heading('03  Image record')
    if data['image_bytes']:
        story.append(ImageComparison(data,width)); story.append(Spacer(1,10))
        story.append(p('Green boxes identify source-derived regions of interest, not confirmed cancer.' if data['boxes'] else 'No region of interest is drawn for this report.','small'))
    story.append(p(data['image_note'],'small'))
    if sample:
        table([['ATTACHMENT\n'+sample.filename,'DIMENSIONS\n'+str(sample.width)+' x '+str(sample.height)+' pixels']])
    heading('04  Quality & interpretation')
    field('Quality outcome',quality.reason if quality else 'Quality check has not been completed.')
    if quality and quality.details.get('checks'):
        rows=[['TECHNICAL CHECK','RESULT']]
        for check in quality.details['checks']:
            rows.append([check.get('label',check.get('name','Check')),('Passed: ' if check.get('passed') else 'Attention: ')+check.get('detail','')])
        table(rows,[width*.29,width*.71],compact=True)
        story.append(Spacer(1,7))
    field('Findings',result.get('findings') or (assessment.finding if assessment else 'Withheld pending an adequate image and completed assessment.'))
    field('Interpretation limits',result.get('limitations') or 'The report does not establish a complete breast examination or diagnosis. No lesion measurements, BI-RADS category, probability score or pathology result has been inferred.')
    story.append(PageBreak())
    story.append(p('Specialist response','title'))
    if data['signed']:
        heading('05  Recorded signed review')
        for review in data['signed']:
            field('Assessment',review.assessment)
            field('Recommendation',review.recommendation)
            field('Review recorded under',person(review.reviewer)+' | '+stamp(review.signed_at))
    elif data['response']:
        table([['RESPONSE STATUS','Predefined specialist opinion - not signed by a clinician'],['CONTENT VERSION',RESPONSE_VERSION]])
        heading('05  Specialist response & recommendation')
        if data['outcome']=='NON_SUSPICIOUS' and data['boxes']:
            field('Image correlation','A localized source-annotated region is present and shown for review. Its presence does not by itself determine a clinical diagnosis.')
        for label,text in data['response']: story.extend([p(label.upper(),'label'),p(text,'response')])
    else:
        heading('05  Specialist review status')
        field('Current position','No signed specialist review is available. A predefined response is not supplied for this case or stage.')
    field('Record status',f'{len(data["reviews"])} specialist review request(s) recorded. '+('A signed review is present in the case record.' if data['signed'] else 'No specialist review has been signed. Exporting this report does not complete a pending review.'))
    legend_start = len(story)
    heading('Assessment colours & interpretation')
    key_rows=[]
    for item in LEGEND:
        label=Paragraph('<font color="'+item['color']+'"><b>'+escape(item['label'])+'</b></font>',styles['small'])
        key_rows.append([label,p(item['meaning'],'small')])
    key_table=Table(key_rows,colWidths=[width*.36,width*.64])
    key_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.3,LINE),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story.append(key_table)
    story.append(Spacer(1,8))
    story.append(p('Ring fill shows classification confidence; the gap is the remainder to 100%. Demo scores are predefined, not cancer probabilities. Colours describe the impression, not confidence thresholds. Green image outlines mark regions of interest, not benignity.','small'))
    story[legend_start:] = [KeepTogether(story[legend_start:])]
    story.append(PageBreak())
    story.append(p('Care plan & case history','title'))
    heading('06  Recorded care plan')
    if data['referral']:
        r=data['referral']
        field('Referral',r.destination+' | Urgency: '+(r.get_urgency_display() or 'Not recorded'))
        field('Referral stage',r.get_status_display())
        if r.appointment_date: field('Recorded appointment',r.appointment_date.strftime('%d %b %Y'))
        field('Reason & requested evaluation',r.reason)
        for update in r.updates.select_related('actor').order_by('created_at','pk'):
            field(update.get_status_display()+' | '+stamp(update.created_at),update.notes)
            story.append(p('Recorded by '+person(update.actor),'small'))
        field('Confirmation',person(r.confirmed_by)+' | '+stamp(r.confirmed_at))
        story.append(p('Referral progress reflects updates recorded by the facility. This workspace does not transmit referrals or book appointments.','small'))
    for followup in data['followups']:
        field('Follow-up: '+followup.due_date.strftime('%d %b %Y'),followup.notes)
        if followup.completed_at and followup.outcome:
            field('Recorded outcome',followup.outcome)
            story.append(p('Recorded by '+person(followup.completed_by),'small'))
        story.append(p('Completed '+stamp(followup.completed_at) if followup.completed_at else 'Scheduled; completion not recorded.','small'))
    if not data['referral'] and not data['followups'] and not data['decisions']:
        field('Current plan','No referral or follow-up plan has been confirmed. '+('An adequate image is required before assessment can continue.' if data['outcome']=='QUALITY_FAILURE' else 'The responsible clinician must review the case and record the next step.'))
    for decision in data['decisions']:
        field(decision.get_action_display(),decision.notes)
        if decision.action=='ROUTINE': field('Routine-care plan and return advice',decision.details.get('safety_net'))
        if decision.action=='SPECIALIST': field('Review question',decision.details.get('reason'))
        story.append(p(person(decision.actor)+' | '+stamp(decision.created_at),'small'))
    heading('07  Case milestones')
    for event in data['events']:
        story.append(p(stamp(event.created_at)+' | '+event.kind.replace('_',' ').capitalize().replace('Ai ','AI ')+' | '+person(event.actor),'small'))
    if not data['events']: story.append(p('No milestones recorded.'))
    heading('08  Report provenance')
    story.append(p('Report revision '+data['revision']+' identifies the exported content. Template '+REPORT_VERSION+'; generated '+stamp(data['generated_at'])+'. Predefined responses are presentation content and do not create a signed review or change the case status.','small'))
    if sample:
        story.append(p('Image attribution: '+sample.attribution+' Source: '+sample.source_url+' Licence: '+sample.licence_url+'. Source filename: '+sample.source_filename+'.','small'))
    story.append(p('Image annotations derive from the matching dataset masks. The uncertain pathway is a controlled workflow example, not a measured confidence level.','small'))
    story.append(p('Clinical wording reference: ACR/RSNA RadiologyInfo, Breast Ultrasound. https://www.radiologyinfo.org/en/info/breastus (reviewed 25 Sep 2026). This reference does not validate this prototype or its individual responses.','small'))
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=73,bottomMargin=66,title='VanaraOncoScan case report - '+case.patient.reference,author='Vanara Health Technologies',pageCompression=1)
    doc.build(story,canvasmaker=lambda *a,**kw:NumberedCanvas(*a,report_meta={'reference':case.patient.reference+' | '+str(case.pk)[:8].upper(),'revision':data['revision']},**kw))
    return output.getvalue()
