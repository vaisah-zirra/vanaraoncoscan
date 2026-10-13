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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, CondPageBreak, Flowable, KeepTogether

from apps.clinical.models import AIAssessment, QualityAssessment
from apps.workflow.models import Referral
from apps.workflow.specialist_content import specialist_content
from apps.workflow.report_content import RESPONSES, RESPONSE_VERSION

from apps.clinical.presentation import assessment_display, LEGEND
from apps.workflow.confidence_pdf import ConfidenceCard
from apps.clinical.report_library import report_for_assessment, REPORT_VERSION as US_REPORT_VERSION, TELERADIOLOGY_THRESHOLD, BIRADS

REPORT_VERSION = '2.0'
NOTICE = 'Investigational AI · Not for clinical diagnosis'
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
            data['image_note'] = 'Original source pixels retained.'
            if result.get('sample_id') == sample.pk and result.get('image_sha256') == sample.sha256:
                data['boxes'] = [b for b in result.get('boxes',[]) if all(isinstance(b.get(k), (int,float)) for k in ('x','y','width','height')) and b['x'] >= 0 and b['y'] >= 0 and b['width'] > 0 and b['height'] > 0 and b['x']+b['width'] <= sample.width and b['y']+b['height'] <= sample.height]
            elif result:
                data['image_note'] += ' Assessment annotations are unavailable because the stored image reference does not match.'
        except (OSError, ValueError, PILImage.DecompressionBombError):
            data['image_note'] = 'Image unavailable for export: the file is missing, unreadable or no longer matches its stored integrity record. No replacement image or annotation has been supplied.'
    data['report'] = report_for_assessment(assessment, attachment) if assessment and not quality_failed else None
    snapshot = {
        'us_report':US_REPORT_VERSION if data['report'] else None,
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
        sample = data['sample']
        cell = (width - 12) / 2
        self.height = min(205, (cell - 16) * sample.height / sample.width + 36)

    def draw(self):
        c = self.canv
        sample = self.data['sample']
        cell = (self.width - 12) / 2
        for index, label in enumerate(('ORIGINAL', 'AI ANNOTATION')):
            x = index * (cell + 12)
            c.setFillColor(colors.HexColor('#0f2622')); c.roundRect(x, 0, cell, self.height, 7, fill=1, stroke=0)
            c.setFillColor(colors.HexColor('#9fc9bb')); c.setFont('Report-Bold', 6.5); c.drawString(x + 10, self.height - 15, label)
            scale = min((cell - 16) / sample.width, (self.height - 32) / sample.height)
            iw, ih = sample.width * scale, sample.height * scale
            ox, oy = x + (cell - iw) / 2, (self.height - 24 - ih) / 2 + 2
            c.drawImage(ImageReader(BytesIO(self.data['image_bytes'])), ox, oy, iw, ih)
            if index:
                for n, box in enumerate(self.data['boxes'], 1):
                    bx, by = ox + box['x'] * scale, oy + (sample.height - box['y'] - box['height']) * scale
                    c.setStrokeColor(colors.HexColor('#65e1b5')); c.setLineWidth(1.4)
                    c.rect(bx, by, box['width'] * scale, box['height'] * scale, fill=0, stroke=1)
                    tag = f'Lesion {n}'
                    tw = pdfmetrics.stringWidth(tag, 'Report-Bold', 6) + 8
                    ty = min(by + box['height'] * scale + 2, oy + ih - 11)
                    c.setFillColor(colors.HexColor('#167958')); c.rect(bx, ty, tw, 10, fill=1, stroke=0)
                    c.setFillColor(colors.white); c.setFont('Report-Bold', 6); c.drawString(bx + 4, ty + 3, tag)


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
            # Approved artwork, background removed (static/brand/vanaraoncoscan-logo.png).
            logo = Path(__file__).resolve().parents[2] / 'static/brand/vanaraoncoscan-logo.png'
            self.drawImage(str(logo), 42, A4[1]-50, width=150, height=150*166/640, mask='auto')
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


CAT_COLORS = {'0': '#9A650D', '1': '#23788A', '2': '#23788A', '3': '#19765B', '4A': '#B54D25', '4B': '#B54D25', '4C': '#B54D25', '5': '#A8324A', '6': '#A8324A'}
SIGNAL_COLORS = {'benign': '#19765B', 'suspicious': '#B54D25', 'neutral': '#6B7F7F'}


def draw_confidence_ring(c, cx, cy, r, display, width=5):
    """Confidence ring sized so any value (e.g. 61.7%) sits fully inside the arc."""
    c.saveState()
    c.setLineWidth(width); c.setStrokeColor(colors.HexColor('#e8eeec'))
    c.circle(cx, cy, r, fill=0, stroke=1)
    if display.get('has_score'):
        c.setStrokeColor(colors.HexColor(display['color'])); c.setLineCap(1)
        c.arc(cx - r, cy - r, cx + r, cy + r, startAng=90, extent=-3.6 * float(display['score']))
        value = f"{display['score']}%"
        inner = 2 * (r - width) - 8
        size = 15
        while size > 7 and pdfmetrics.stringWidth(value, 'Report-Bold', size) > inner:
            size -= .5
        c.setFillColor(INK); c.setFont('Report-Bold', size); c.drawCentredString(cx, cy - size * .36, value)
    else:
        c.setFillColor(MUTED); c.setFont('Report-Bold', 11); c.drawCentredString(cx, cy - 4, 'N/A')
    c.restoreState()


class ResultSummary(Flowable):
    """Page-one result band: BI-RADS tile, AI impression, confidence ring and specialist status."""
    def __init__(self, data, width, styles):
        super().__init__()
        self.data, self.width, self.styles = data, width, styles
        self.height = 132

    def draw(self):
        c = self.canv; d = self.data; display = d['display']; rep = d.get('report')
        tone = colors.HexColor(display['color'])
        c.saveState()
        path = c.beginPath(); path.roundRect(0, 0, self.width, self.height, 10); c.clipPath(path, stroke=0, fill=0)
        c.setFillColor(colors.white); c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        c.setFillColor(tone); c.rect(0, 0, 5, self.height, fill=1, stroke=0)
        c.restoreState()
        c.setStrokeColor(LINE); c.setLineWidth(.8); c.roundRect(0, 0, self.width, self.height, 10, fill=0, stroke=1)
        x = 22
        final = d.get('final_birads')
        if rep or final:
            code = final or rep['birads']['category']
            cat = colors.HexColor(CAT_COLORS.get(code, '#183d3d'))
            c.setFillColor(cat); c.roundRect(x, 22, 88, 88, 9, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont('Report-Bold', 7); c.drawCentredString(x + 44, 94, 'FINAL BI-RADS' if final else 'BI-RADS')
            c.setFont('Report-Bold', 34 if len(code) == 1 else 28); c.drawCentredString(x + 44, 52, code)
            c.setFont('Report', 6.3)
            if final:
                c.drawCentredString(x + 44, 32, 'SPECIALIST CONFIRMED')
            elif rep['birads']['provisional']:
                c.drawCentredString(x + 44, 32, 'PROVISIONAL')
            x += 104
        text_w = self.width - x - 128
        y = self.height - 18

        def para(text, style, top):
            p = Paragraph(text, self.styles[style]); _, h = p.wrap(text_w, 200); p.drawOn(c, x, top - h); return top - h
        y = para('AI ASSESSMENT · ' + escape(d['model']), 'eyebrow', y) - 3
        y = para(f'<font color="{display["color"]}">{escape(display["label"])}</font>', 'summary_title', y) - 3
        if final:
            name, likelihood, _ = BIRADS.get(final, ('', '', ''))
            y = para(f'<b>Final: BI-RADS {escape(final)} – {escape(name)}</b> · Likelihood of malignancy {escape(likelihood)}', 'summary_body', y) - 2
            if rep:
                b = rep['birads']
                y = para(f'<font color="#607b77">AI category: BI-RADS {b["category"]}{" (provisional)" if b["provisional"] else ""} – {escape(b["name"])}</font>', 'summary_body', y) - 4
        elif rep:
            b = rep['birads']
            y = para(f'<b>BI-RADS {b["category"]}{" (provisional)" if b["provisional"] else ""} – {escape(b["name"])}</b> · Likelihood of malignancy {escape(b["likelihood"])}', 'summary_body', y) - 4
        else:
            y = para(escape(display['meaning']), 'summary_body', y) - 4
        para(d['specialist_line'], 'summary_body', y)
        cx = self.width - 64
        draw_confidence_ring(c, cx, 76, 30, display)
        c.setFillColor(INK); c.setFont('Report-Bold', 7.5); c.drawCentredString(cx, 32, 'Model confidence')
        c.setFillColor(MUTED); c.setFont('Report', 6.5); c.drawCentredString(cx, 22, 'VOS-BUS v0.9' if display.get('has_score') else 'Not available')


class Callout(Flowable):
    """Tinted box with a coloured left rule, wrapping arbitrary paragraphs."""
    def __init__(self, flowables, width, tint='#f3f8f6', rule='#147c70', pad=12):
        super().__init__()
        self.items, self.width, self.tint, self.rule, self.pad = flowables, width, tint, rule, pad

    def wrap(self, aw, ah):
        self.inner = self.width - 2 * self.pad - 4
        self.sizes = [f.wrap(self.inner, ah) for f in self.items]
        self.height = sum(h for _, h in self.sizes) + 2 * self.pad + 4 * (len(self.items) - 1)
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor(self.tint)); c.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(self.rule)); c.rect(0, 0, 3, self.height, fill=1, stroke=0)
        y = self.height - self.pad
        for f, (_, h) in zip(self.items, self.sizes):
            f.drawOn(c, self.pad + 4, y - h); y -= h + 4


def render_report(data):
    output = BytesIO()
    width = A4[0] - 84
    base = dict(fontName='Report', textColor=INK)
    styles = {
        'doc_title': ParagraphStyle('doc_title', fontName='Report-Bold', fontSize=21, leading=25, textColor=INK, spaceAfter=2),
        'title': ParagraphStyle('title', fontName='Report-Bold', fontSize=17, leading=21, textColor=INK, spaceBefore=2, spaceAfter=4),
        'eyebrow': ParagraphStyle('eyebrow', fontName='Report-Bold', fontSize=6.8, leading=9, textColor=TEAL),
        'section': ParagraphStyle('section', fontName='Report-Bold', fontSize=10, leading=13, textColor=TEAL, spaceBefore=16, spaceAfter=6, keepWithNext=True),
        'h': ParagraphStyle('h', fontName='Report-Bold', fontSize=10.5, leading=14, textColor=INK, spaceBefore=10, spaceAfter=5, keepWithNext=True),
        'label': ParagraphStyle('label', fontName='Report-Bold', fontSize=6.8, leading=9, textColor=MUTED, spaceAfter=2, keepWithNext=True),
        'body': ParagraphStyle('body', fontSize=8.8, leading=13.2, spaceAfter=6, splitLongWords=True, **base),
        'list': ParagraphStyle('list', fontSize=8.8, leading=13, spaceAfter=3.5, leftIndent=14, firstLineIndent=-14, **base),
        'small': ParagraphStyle('small', fontSize=7.2, leading=10.2, textColor=MUTED, spaceAfter=4, fontName='Report'),
        'cell': ParagraphStyle('cell', fontSize=7.8, leading=10.6, **base),
        'cell_b': ParagraphStyle('cell_b', fontName='Report-Bold', fontSize=7.8, leading=10.6, textColor=INK),
        'cell_m': ParagraphStyle('cell_m', fontSize=7, leading=9.6, textColor=MUTED, fontName='Report'),
        'th': ParagraphStyle('th', fontName='Report-Bold', fontSize=6.5, leading=8.5, textColor=MUTED),
        'summary_title': ParagraphStyle('summary_title', fontName='Report-Bold', fontSize=14.5, leading=18, textColor=INK),
        'summary_body': ParagraphStyle('summary_body', fontSize=8, leading=11.2, **base),
        'meta_l': ParagraphStyle('meta_l', fontName='Report-Bold', fontSize=6.3, leading=8, textColor=MUTED),
        'meta_v': ParagraphStyle('meta_v', fontName='Report-Bold', fontSize=8.4, leading=11, textColor=INK),
    }
    def txt(value):
        return escape(str(value if value not in (None, '') else 'Not recorded')).replace('\n', '<br/>')
    def p(text, style='body'):
        return Paragraph(txt(text), styles[style])
    def raw(markup, style='body'):
        return Paragraph(markup, styles[style])
    story = []
    def section(title): story.append(p(title, 'section'))
    def heading(text): story.append(p(text, 'h'))
    def field(label, text): story.extend([p(label.upper(), 'label'), p(text)])
    def numbered(lines):
        for i, line in enumerate(lines, 1):
            story.append(raw(f'<b>{i}.</b>&nbsp;&nbsp;{txt(line)}', 'list'))
    def grid(rows, widths, header=True, zebra=False, pad=6):
        t = Table(rows, colWidths=widths, hAlign='LEFT', repeatRows=1 if header else 0)
        style = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                 ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
                 ('LINEBELOW', (0, 0), (-1, -1), .4, LINE), ('LINEABOVE', (0, 0), (-1, 0), .8, INK if header else LINE)]
        if header:
            style += [('BACKGROUND', (0, 0), (-1, 0), PALE), ('LINEBELOW', (0, 0), (-1, 0), .6, INK)]
        t.setStyle(TableStyle(style))
        story.append(t)
    def th(*cells): return [Paragraph(escape(c.upper()), styles['th']) for c in cells]

    case = data['case']; quality = data['quality']; assessment = data['assessment']; result = data['result']; sample = data['sample']
    rep = data.get('report'); display = data['display']; signed = data['signed']
    pending = [r for r in data['reviews'] if not r.signed_at]
    data['model'] = rep['model'] if rep else 'VOS-BUS v0.9.4 (investigational)'
    data['final_birads'] = signed[-1].birads if signed and signed[-1].birads in BIRADS else None
    if signed:
        s = signed[-1]
        data['specialist_line'] = (f'<b>Teleradiology:</b> signed by {escape(person(s.reviewer))}'
                                   + (f' · <b>final BI-RADS {escape(s.birads)}</b>' if s.birads else '')
                                   + (f' · {escape(s.get_concordance_display())}' if s.concordance else ''))
    elif pending:
        data['specialist_line'] = '<b>Teleradiology:</b> second read requested, awaiting specialist signature.'
    elif data['outcome'] == 'QUALITY_FAILURE':
        data['specialist_line'] = '<b>Interpretation withheld:</b> the image did not pass the quality check.'
    else:
        data['specialist_line'] = '<b>Teleradiology:</b> no second read requested.'

    # ---------------------------------------------------------------- Page 1: result at a glance
    title_row = Table([[[raw('AI-ASSISTED BREAST ULTRASOUND · CASE REPORT', 'eyebrow'), Spacer(1, 4), p('Breast ultrasound report', 'doc_title')],
                        raw(f'<para alignment="right"><font size="7" color="#607b77"><b>STATUS</b></font><br/><b>{txt(case.get_status_display())}</b></para>', 'body')]],
                      colWidths=[width - 150, 150])
    title_row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
    story += [title_row, Spacer(1, 10)]
    def meta(label, value): return [Paragraph(escape(label), styles['meta_l']), Paragraph(txt(value), styles['meta_v'])]
    study = sample.study_id if sample else 'No image attached'
    meta_rows = [[meta('PATIENT', case.patient.display_name), meta('PATIENT REFERENCE', case.patient.reference), meta('STUDY', study), meta('REPORT DATE', stamp(data['generated_at']))],
                 [meta('FACILITY', case.patient.facility.name), meta('CASE REFERENCE', str(case.pk)[:8].upper()), meta('EXAMINATION', 'Targeted breast ultrasound'), meta('AI MODEL', data['model'].replace(' (investigational)', ''))]]
    mt = Table(meta_rows, colWidths=[width * .27, width * .23, width * .24, width * .26])
    mt.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                            ('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, -1), (-1, -1), .4, LINE)]))
    story += [mt, Spacer(1, 14)]
    if assessment or data['outcome'] == 'QUALITY_FAILURE':
        story.append(ResultSummary(data, width, styles))
    else:
        story.append(Callout([p('Assessment not yet completed.', 'h'), p('Complete the image-quality check and AI assessment to obtain a result.', 'small')], width, tint='#f4f6f6', rule='#677582'))
    story.append(Spacer(1, 6))

    section('Key images')
    if data['image_bytes']:
        story.append(ImageComparison(data, width))
        story.append(Spacer(1, 4))
        story.append(p(('Annotated view: AI-detected lesion boundary. ' if data['boxes'] else 'No lesion was detected, so no region is marked. ') + data['image_note'], 'small'))
    else:
        story.append(p(data['image_note'], 'small'))

    section('Clinical indication')
    story.append(p(case.presenting_concern or 'History has not been recorded.'))

    if data['outcome'] == 'QUALITY_FAILURE':
        section('Interpretation')
        story.append(Callout([p('Assessment withheld', 'h'), p('Diagnostic interpretation is withheld because the recorded quality check did not pass. Image-quality failure must not be interpreted as a normal or reassuring finding; obtain an adequate acquisition and repeat the quality check.')], width, tint='#fdf5e7', rule='#9A650D'))
    elif rep:
        if signed:
            s = signed[-1]
            section('Final impression · specialist second read')
            story.append(Callout([p(s.assessment), raw(f'<font color="#607b77">Signed by {txt(person(s.reviewer))}, teleradiology, {txt(stamp(s.signed_at))}. Full second-read report on the specialist response page.</font>', 'small')],
                                 width, tint='#eef7f2', rule=CAT_COLORS.get(s.birads, '#147c70')))
        section('AI impression' if signed else 'Impression')
        numbered(rep['impression'])
        section('AI recommendations' if signed else 'Recommendations')
        numbered(rep['recommendations'])
    elif assessment:
        section('Impression')
        story.append(p(result.get('impression') or assessment.finding))

    # ---------------------------------------------------------------- Structured findings
    if rep:
        story.append(CondPageBreak(260))
        story.append(Spacer(1, 18))
        story.append(raw('DETAILED FINDINGS · ACR BI-RADS® ULTRASOUND LEXICON', 'eyebrow'))
        story.append(p('Structured ultrasound report', 'title'))
        section('Examination')
        grid([[p('Technique', 'cell_b'), p(rep['technique'], 'cell')], [p('Comparison', 'cell_b'), p(rep['comparison'], 'cell')],
              [p('Background echotexture', 'cell_b'), p(rep['composition'], 'cell')],
              [p('Image quality', 'cell_b'), p('Technical checks passed (integrity, decoding, dimensions, resolution).' if quality and quality.adequate else 'Not passed.', 'cell')]],
             [width * .24, width * .76], header=False)
        section('Findings')
        for lesion in rep['lesions']:
            counts = lesion['counts']
            story.append(p(f'{lesion["label"]} · {lesion["type"]}', 'h'))
            story.append(raw(f'<font color="#19765B"><b>{counts["benign"]} favour benign</b></font>&nbsp;&nbsp;·&nbsp;&nbsp;<font color="#B54D25"><b>{counts["suspicious"]} suspicious</b></font>&nbsp;&nbsp;·&nbsp;&nbsp;<font color="#6B7F7F"><b>{counts["neutral"]} non-discriminating</b></font>', 'small'))
            story.append(p(lesion['location'], 'small'))
            rows = [th('Lexicon feature', 'Finding', 'Significance')]
            for dsc in lesion['descriptors']:
                colour = SIGNAL_COLORS[dsc['signal']]
                rows.append([p(dsc['feature'], 'cell_b'), [p(dsc['finding'], 'cell_b'), p(dsc['note'], 'cell_m')],
                             raw(f'<font color="{colour}"><b>• {escape(dsc["signal_label"])}</b></font>', 'cell')])
            grid(rows, [width * .2, width * .58, width * .22])
        if not rep['lesions']:
            for line in rep.get('normal_findings', []):
                story.append(raw('•&nbsp;&nbsp;' + txt(line), 'list'))
        if rep['morphometric_rows']:
            section('Quantitative lesion analysis')
            grid([th('Measure', 'Value', 'Interpretation')] + [[p(a, 'cell_b'), p(b, 'cell'), p(c_, 'cell_m')] for a, b, c_ in rep['morphometric_rows']],
                 [width * .24, width * .18, width * .58])
        if rep['differential']:
            section('Differential diagnosis')
            grid([th('Diagnosis', 'Likelihood', 'Supporting features')] + [[p(a, 'cell_b'), p(b, 'cell'), p(c_, 'cell_m')] for a, b, c_ in rep['differential']],
                 [width * .32, width * .15, width * .53])
        section('How the AI reached this result')
        story.append(Callout([p(rep['reasoning'])], width))
        story.append(Spacer(1, 4))
        story.append(p('Generated by ' + rep['model'] + '. Lesion metrics are computed from the segmentation outline; pixel spacing is not stored with the source image, so sizes are given in pixels.', 'small'))

    # ---------------------------------------------------------------- Specialist second read
    story.append(CondPageBreak(330))
    story.append(Spacer(1, 18))
    story.append(raw('SPECIALIST INPUT · TELERADIOLOGY', 'eyebrow'))
    story.append(p('Specialist response', 'title'))
    if signed:
        for review in signed:
            section('Signed teleradiology review')
            chips = Table([[meta('CONCORDANCE WITH AI', review.get_concordance_display() or 'Not recorded'),
                            meta('FINAL BI-RADS CATEGORY', ('BI-RADS ' + review.birads) if review.birads else 'Not recorded'),
                            meta('SIGNED', stamp(review.signed_at))]], colWidths=[width / 3] * 3)
            chips.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                                       ('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, 0), (-1, 0), .4, LINE)]))
            story += [chips, Spacer(1, 8)]
            if review.findings: field('Findings', review.findings)
            field('Impression' if review.findings else 'Assessment', review.assessment)
            field('Recommendation', review.recommendation)
            sig = Table([[raw(f'<b>{txt(person(review.reviewer))}</b><br/><font color="#607b77" size="7">Teleradiology · electronically signed {txt(stamp(review.signed_at))}</font>', 'body')]], colWidths=[width * .5], hAlign='LEFT')
            sig.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 6)]))
            story += [Spacer(1, 8), KeepTogether([raw('SIGNED BY', 'label'), sig])]
    else:
        section('Specialist review status')
        if data['outcome'] == 'QUALITY_FAILURE':
            field('Interpretation status', 'Diagnostic interpretation is withheld because the recorded quality check did not pass. Image-quality failure must not be interpreted as a normal or reassuring finding.')
        field('Current position', 'A teleradiology second read was requested on ' + stamp(pending[0].requested_at) + ' and is awaiting a specialist signature.' if pending else 'No teleradiology review has been requested for this case.')
    story.append(p(f'{len(data["reviews"])} specialist review request(s) recorded. ' + ('A signed review is present in the case record.' if signed else 'No specialist review has been signed. Exporting this report does not complete a pending review.'), 'small'))
    if rep:
        section('Patient-friendly explanation')
        story.append(Callout([p(rep.get('patient_summary_reviewed') if signed and rep.get('patient_summary_reviewed') else rep['patient_summary']), p('Plain-language wording for clinicians to adapt when explaining the result; not a substitute for a consultation.', 'small')], width, tint='#f6f8fb', rule='#23788A'))

    # ---------------------------------------------------------------- Care plan & record
    section('Recorded care plan')
    if data['referral']:
        r = data['referral']
        grid([[meta('RECEIVING SERVICE', r.destination), meta('URGENCY', r.get_urgency_display() or 'Not recorded'), meta('REFERRAL STAGE', r.get_status_display())]], [width / 3] * 3, header=False)
        story.append(Spacer(1, 6))
        if r.appointment_date: field('Recorded appointment', r.appointment_date.strftime('%d %b %Y'))
        field('Reason & requested evaluation', r.reason)
        for update in r.updates.select_related('actor').order_by('created_at', 'pk'):
            field(update.get_status_display() + ' | ' + stamp(update.created_at), update.notes)
            story.append(p('Recorded by ' + person(update.actor), 'small'))
        field('Confirmation', person(r.confirmed_by) + ' | ' + stamp(r.confirmed_at))
        story.append(p('Referral progress reflects updates recorded by the facility.', 'small'))
    for followup in data['followups']:
        field('Follow-up: ' + followup.due_date.strftime('%d %b %Y'), followup.notes)
        if followup.completed_at and followup.outcome:
            field('Recorded outcome', followup.outcome)
            story.append(p('Recorded by ' + person(followup.completed_by), 'small'))
        story.append(p('Completed ' + stamp(followup.completed_at) if followup.completed_at else 'Scheduled; completion not recorded.', 'small'))
    if not data['referral'] and not data['followups'] and not data['decisions']:
        story.append(p('No referral or follow-up plan has been confirmed. ' + ('An adequate image is required before assessment can continue.' if data['outcome'] == 'QUALITY_FAILURE' else 'The responsible clinician must review the case and record the next step.')))
    for decision in data['decisions']:
        field(decision.get_action_display(), decision.notes)
        if decision.action == 'ROUTINE': field('Routine-care plan and return advice', decision.details.get('safety_net'))
        if decision.action == 'SPECIALIST': field('Review question', decision.details.get('reason'))
        story.append(p(person(decision.actor) + ' | ' + stamp(decision.created_at), 'small'))

    if quality and quality.details.get('checks'):
        section('Technical quality checks')
        story.append(p(quality.reason, 'small'))
        grid([th('Check', 'Result')] + [[p(ch.get('label', ch.get('name', 'Check')), 'cell_b'), raw(('<font color="#19765B"><b>Passed</b></font> · ' if ch.get('passed') else '<font color="#B54D25"><b>Attention</b></font> · ') + txt(ch.get('detail', '')), 'cell')] for ch in quality.details['checks']],
             [width * .26, width * .74], pad=3.5)
    elif quality:
        section('Image quality')
        story.append(p(quality.reason))

    section('Case timeline')
    if data['events']:
        grid([th('Date & time', 'Milestone', 'Recorded by')] + [[p(stamp(e.created_at), 'cell'), p(e.kind.replace('_', ' ').capitalize().replace('Ai ', 'AI '), 'cell_b'), p(person(e.actor), 'cell')] for e in data['events']],
             [width * .28, width * .44, width * .28], pad=3.5)
    else:
        story.append(p('No milestones recorded.'))

    key = [p('Assessment colours & interpretation', 'section')]
    key_rows = [[raw(f'<font color="{item["color"]}"><b>• {escape(item["label"])}</b></font>', 'cell'), p(item['meaning'], 'cell_m')] for item in LEGEND]
    kt = Table(key_rows, colWidths=[width * .34, width * .66])
    kt.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), .3, LINE), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    key += [kt, Spacer(1, 4), p('The ring shows model confidence; the gap is the remainder to 100%. Confidence scores express classification certainty, not cancer probabilities. Colours describe the impression, not confidence thresholds.', 'small')]
    story.append(KeepTogether(key))

    section('Report provenance')
    story.append(p('Report revision ' + data['revision'] + ' · template ' + REPORT_VERSION + ' · generated ' + stamp(data['generated_at']) + '. Exporting a report does not sign a review or change the case status. '
                   'Bounding boxes enclose the segmented lesion region; cases below the ' + str(TELERADIOLOGY_THRESHOLD) + '% confidence threshold are routed for teleradiology review. '
                   'Lexicon: ACR BI-RADS® Atlas, 5th edition (ultrasound). Wording reference: ACR/RSNA RadiologyInfo, Breast Ultrasound; this reference does not validate this software or its individual outputs.', 'small'))
    if sample:
        story.append(p('Image source: ' + sample.attribution + ' Licence: CC BY 4.0 (' + sample.licence_url + '). Original pixels unchanged.', 'small'))

    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=70, bottomMargin=62,
                            title='VanaraOncoScan breast ultrasound report - ' + case.patient.reference, author='Vanara Multi-Ventures', pageCompression=1)
    doc.build(story, canvasmaker=lambda *a, **kw: NumberedCanvas(*a, report_meta={'reference': case.patient.reference + ' | ' + str(case.pk)[:8].upper(), 'revision': data['revision']}, **kw))
    return output.getvalue()
