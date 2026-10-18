"""Branded PDF exports of the validation evidence (full report or a single section)."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable, KeepTogether, CondPageBreak
from apps.workflow.reporting import INK, TEAL, MUTED, PALE, LINE  # also registers the report fonts

GOLD = colors.HexColor('#b8892a')
SOFT = colors.HexColor('#e6efe9')
CORAL = colors.HexColor('#c8613f')
LOGO = Path(__file__).resolve().parents[2] / 'static/brand/vanaraoncoscan-logo.png'
KINDS = {
    'full': ('Validation evidence report', 'VALIDATION EVIDENCE | FULL REPORT'),
    'participants': ('Participants and engagement', 'VALIDATION EVIDENCE | PARTICIPANTS'),
    'feedback': ('Survey responses and feedback', 'VALIDATION EVIDENCE | FEEDBACK'),
    'interest': ('Interest and pipeline', 'VALIDATION EVIDENCE | INTEREST'),
}
W = A4[0] - 84

S = {
    'title': ParagraphStyle('title', fontName='Report-Bold', fontSize=22, leading=26, textColor=INK, spaceAfter=3),
    'sub': ParagraphStyle('sub', fontName='Report', fontSize=9.5, leading=13, textColor=MUTED, spaceAfter=10),
    'eyebrow': ParagraphStyle('eyebrow', fontName='Report-Bold', fontSize=7, leading=9, textColor=TEAL, spaceAfter=3),
    'section': ParagraphStyle('section', fontName='Report-Bold', fontSize=13, leading=17, textColor=INK, spaceBefore=6, spaceAfter=3, keepWithNext=True),
    'h': ParagraphStyle('h', fontName='Report-Bold', fontSize=9.6, leading=13, textColor=TEAL, spaceBefore=10, spaceAfter=5, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Report', fontSize=8.7, leading=13, textColor=INK, spaceAfter=5),
    'bullet': ParagraphStyle('bullet', fontName='Report', fontSize=8.9, leading=13.4, textColor=INK, leftIndent=13, firstLineIndent=-13, spaceAfter=4),
    'small': ParagraphStyle('small', fontName='Report', fontSize=7, leading=10, textColor=MUTED, spaceAfter=4),
    'cell': ParagraphStyle('cell', fontName='Report', fontSize=7.4, leading=10, textColor=INK),
    'cell_b': ParagraphStyle('cell_b', fontName='Report-Bold', fontSize=7.4, leading=10, textColor=INK),
    'cell_m': ParagraphStyle('cell_m', fontName='Report', fontSize=6.7, leading=9, textColor=MUTED),
    'th': ParagraphStyle('th', fontName='Report-Bold', fontSize=6.3, leading=8.2, textColor=MUTED),
    'kpi': ParagraphStyle('kpi', fontName='Report-Bold', fontSize=19, leading=22, textColor=INK),
    'kpi_l': ParagraphStyle('kpi_l', fontName='Report-Bold', fontSize=6.6, leading=8.5, textColor=TEAL),
    'kpi_s': ParagraphStyle('kpi_s', fontName='Report', fontSize=6.7, leading=9, textColor=MUTED),
    'quote': ParagraphStyle('quote', fontName='Report', fontSize=8.6, leading=12.8, textColor=INK),
    'meta_l': ParagraphStyle('meta_l', fontName='Report-Bold', fontSize=6.2, leading=8, textColor=MUTED),
    'meta_v': ParagraphStyle('meta_v', fontName='Report-Bold', fontSize=8, leading=10.5, textColor=INK),
}


def t(value, empty='—'):
    return escape(str(value)) if value not in (None, '') else empty


def P(text, style='body'):
    return Paragraph(text, S[style])


def when(value, fmt='%d %b %Y'):
    return timezone.localtime(value).strftime(fmt) if value else '—'


class Bars(Flowable):
    """Horizontal bar list: label · bar · value. Used for funnels and distributions."""
    def __init__(self, rows, width=W, color=TEAL, label_w=170, show_pct=True, note_key=None, max_value=None):
        super().__init__()
        self.rows, self.width, self.color, self.label_w, self.show_pct, self.note_key = rows, width, color, label_w, show_pct, note_key
        self.max = max_value or max([r['n'] for r in rows] + [1])
        self.row_h = 17
        self.height = len(rows) * self.row_h + 2

    def wrap(self, *args):
        return self.width, self.height

    def draw(self):
        c = self.canv
        bar_x = self.label_w + 8
        bar_w = self.width - bar_x - 92
        for i, row in enumerate(self.rows):
            y = self.height - (i + 1) * self.row_h + 4
            c.setFillColor(INK); c.setFont('Report', 7.6)
            label, room = row['label'], self.label_w - 4
            if c.stringWidth(label, 'Report', 7.6) > room:
                while label and c.stringWidth(label + '…', 'Report', 7.6) > room:
                    label = label[:-1]
                label = label.rstrip() + '…'
            c.drawString(0, y + 2, label)
            c.setFillColor(SOFT); c.roundRect(bar_x, y, bar_w, 9, 3, stroke=0, fill=1)
            filled = bar_w * (row['n'] / self.max) if self.max else 0
            if filled > 0:
                c.setFillColor(row.get('color', self.color)); c.roundRect(bar_x, y, max(filled, 4), 9, 3, stroke=0, fill=1)
            c.setFillColor(INK); c.setFont('Report-Bold', 7.8)
            value = f"{row['n']}"
            c.drawString(bar_x + bar_w + 8, y + 1.5, value)
            extra = ''
            if self.note_key and row.get(self.note_key) is not None:
                extra = f"{row[self.note_key]}% of previous"
            elif self.show_pct and 'pct' in row:
                extra = f"{row['pct']}%"
            if extra:
                c.setFillColor(MUTED); c.setFont('Report', 6.6)
                c.drawString(bar_x + bar_w + 8 + c.stringWidth(value, 'Report-Bold', 7.8) + 5, y + 1.8, extra)


class EvidenceCanvas(canvas.Canvas):
    def __init__(self, *args, meta=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.states, self.meta = [], meta

    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.drawImage(str(LOGO), 42, A4[1] - 50, width=150, height=150 * 166 / 640, mask='auto')
            self.setFillColor(MUTED); self.setFont('Report', 7)
            self.drawRightString(A4[0] - 42, A4[1] - 32, self.meta['band'])
            self.drawRightString(A4[0] - 42, A4[1] - 44, self.meta['reference'])
            self.setStrokeColor(LINE); self.line(42, A4[1] - 55, A4[0] - 42, A4[1] - 55); self.line(42, 50, A4[0] - 42, 50)
            if self.meta['named']:
                self.setFillColor(CORAL); self.setFont('Report-Bold', 7)
                self.drawString(42, 37, 'INTERNAL · CONTAINS PERSONAL CONTACT DETAILS · DO NOT SHARE WITHOUT CONSENT')
            else:
                self.setFillColor(TEAL); self.setFont('Report-Bold', 7)
                self.drawString(42, 37, 'Anonymised validation evidence · Prepared by Vanara Multi-Ventures')
            self.setFillColor(MUTED); self.setFont('Report', 6.5)
            self.drawString(42, 25, f"Generated {self.meta['generated']} · Data fingerprint {self.meta['fingerprint'][:16]}")
            self.drawRightString(A4[0] - 42, 25, f'Page {self._pageNumber} of {total}')
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def table(rows, widths, zebra=True):
    tbl = Table(rows, colWidths=widths, hAlign='LEFT', repeatRows=1)
    style = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
             ('TOPPADDING', (0, 0), (-1, -1), 4.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
             ('BACKGROUND', (0, 0), (-1, 0), PALE), ('LINEBELOW', (0, 0), (-1, 0), .6, INK), ('LINEBELOW', (0, 1), (-1, -1), .3, LINE)]
    if zebra:
        style += [('BACKGROUND', (0, i), (-1, i), colors.HexColor('#fafcfb')) for i in range(2, len(rows), 2)]
    tbl.setStyle(TableStyle(style))
    return tbl


def th(*cells):
    return [P(escape(c.upper()), 'th') for c in cells]


def kpis(items):
    cells = [[P(t(v), 'kpi'), P(escape(l.upper()), 'kpi_l'), P(t(s, ''), 'kpi_s')] for v, l, s in items]
    tbl = Table([cells], colWidths=[W / len(items)] * len(items), hAlign='LEFT')
    tbl.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), .5, LINE), ('INNERGRID', (0, 0), (-1, -1), .5, LINE),
                             ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f6faf8')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                             ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9), ('LEFTPADDING', (0, 0), (-1, -1), 10)]))
    return tbl


def callout(lines, title='KEY FINDINGS'):
    inner = [P(title, 'eyebrow')] + [P(f'<font color="#147c70"><b>•</b></font>&nbsp;&nbsp;{escape(line)}', 'bullet') for line in lines]
    tbl = Table([[inner]], colWidths=[W])
    tbl.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eef6f2')), ('LINEBEFORE', (0, 0), (0, -1), 3, TEAL),
                             ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
                             ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    return tbl


def none(text='Nothing recorded for this cohort yet.'):
    return P(f'<i>{escape(text)}</i>', 'small')


def render(d, kind='full'):
    title, band = KINDS[kind]
    named = d['identity'] == 'named'
    story = []
    add = story.append

    # ---- Cover block -------------------------------------------------------
    add(P('VANARAONCOSCAN · AI-SUPPORTED BREAST ULTRASOUND · PILOT MVP', 'eyebrow'))
    add(P(escape(title), 'title'))
    add(P('Evidence recorded in the VanaraOncoScan pilot workspace: who tried the platform, how far they got, what they said, '
          'and who asked for a next step.', 'sub'))
    meta = [('PERIOD', d['filters']['period']), ('SOURCE', d['filters']['source']), ('ROLE', d['filters']['role']),
            ('GENERATED', when(d['generated'], '%d %b %Y, %H:%M')), ('IDENTITY', 'Named (internal)' if named else 'Anonymised'), ('REFERENCE', d['reference'])]
    mt = Table([[[P(l, 'meta_l'), P(t(v), 'meta_v')] for l, v in meta]], colWidths=[W * .13, W * .14, W * .14, W * .18, W * .16, W * .25], hAlign='LEFT')
    mt.setStyle(TableStyle([('LINEABOVE', (0, 0), (-1, 0), .8, INK), ('LINEBELOW', (0, 0), (-1, 0), .4, LINE),
                            ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    add(mt); add(Spacer(1, 12))

    sv, comp, it, tot = d['survey'], d['completion'], d['interest'], d['totals']
    if kind in ('full', 'participants'):
        add(kpis([(tot['participants'], 'Participants', f"{tot['organisations']} organisations"),
                  (comp['finishers'], 'Completed the journey', f"{comp['rate']}% of {comp['rounds']} rounds"),
                  (f"{sv['average']:.1f}/5" if sv['average'] is not None else '—', 'Usefulness rating', f"{sv['n']} responses · {sv['top2']}% gave 4–5"),
                  (it['n'], 'Enquiries', f"{it['pilots']} pilot · {it['demos']} demo")]))
    elif kind == 'feedback':
        add(kpis([(sv['n'], 'Survey responses', f"from {sv['respondents']} participants"),
                  (f"{sv['average']:.1f}/5" if sv['average'] is not None else '—', 'Average rating', f"median {sv['median'] if sv['median'] is not None else '—'}"),
                  (f"{sv['top2']}%", 'Rated 4 or 5 stars', f"{sv['low']} rated 1–2"),
                  (sv['wants_next_step'], 'Asked for a next step', f"{sv['contact_ok']} agreed to be contacted")]))
    else:
        add(kpis([(it['n'], 'Enquiries', f"{len(it['organisations'])} organisations"),
                  (it['pilots'], 'Pilot / waitlist', f"{it['demos']} demo requests"),
                  (it['commercial'], 'Commercial interest', 'subscription, pricing, deployment'),
                  (it['tried'], 'Had used the workspace', f"{it['progressed']} progressed past ‘New’")]))
    add(Spacer(1, 12))
    if kind == 'full':
        add(callout(d['findings']))
    elif kind == 'participants':
        add(callout([x for x in d['findings'] if 'enquir' not in x and 'rated' not in x and 'valued' not in x and 'influence' not in x and 'themes' not in x and 'asked for a next step' not in x] or d['findings']))
    elif kind == 'feedback':
        add(callout([x for x in d['findings'] if any(k in x for k in ('rated', 'valued', 'influence', 'themes', 'asked for a next step'))] or ['No survey responses recorded for this cohort yet.']))
    else:
        add(callout([x for x in d['findings'] if 'enquir' in x] or ['No enquiries recorded for this cohort yet.']))
    add(Spacer(1, 6))

    # ---- Participants & engagement ----------------------------------------
    if kind in ('full', 'participants'):
        add(Spacer(1, 10)); add(CondPageBreak(200))
        add(P('01 · ENGAGEMENT', 'eyebrow')); add(P('From first visit to next step', 'section'))
        add(P('Each step counts unique participants in this cohort (landing visits are browser sessions). The note shows the share of the previous step that continued.', 'small'))
        add(Bars(d['funnel'], note_key='conv', label_w=175))
        add(P('Who took part', 'h'))
        roles = Bars(d['roles'], width=W / 2 - 8, label_w=120) if d['roles'] else none()
        srcs = Bars(d['sources'], width=W / 2 - 8, label_w=90, color=colors.HexColor('#2f6f8a')) if d['sources'] else none()
        pair = Table([[[P('BY ROLE', 'eyebrow'), roles], [P('BY HOW THEY FOUND US', 'eyebrow'), srcs]]], colWidths=[W / 2, W / 2], hAlign='LEFT')
        pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
        add(pair)
        if tot['top_orgs']:
            add(P('Organisations represented', 'h'))
            add(P(', '.join(f"{escape(name)} ({n})" for name, n in tot['top_orgs']) + ('…' if tot['organisations'] > len(tot['top_orgs']) else ''), 'body'))

        add(CondPageBreak(180))
        add(P('Walkthrough completion', 'h'))
        rows = [th('Measure', 'Value', 'What it means')]
        med = f"{comp['median_minutes']:g} min" if comp['median_minutes'] is not None else '—'
        for label, value, note in [
            ('Walkthrough rounds', comp['rounds'], 'Cases taken into the workspace by participants'),
            ('Completed rounds', f"{comp['completed']} ({comp['rate']}%)", 'Care plan recorded and case report downloaded'),
            ('Median time to complete', med, 'From starting a case to downloading the report'),
            ('Assessment path / quality path', f"{comp['assessment_path']} / {comp['quality_path']}", 'Quality path: image rejected by the quality check'),
            ('Specialist second reads', comp['specialist_reads'], 'Teleradiology reviews requested or routed automatically'),
            ('Participants who tried more than one case', comp['repeat_users'], 'An indicator of voluntary re-use'),
        ]:
            rows.append([P(escape(label), 'cell_b'), P(t(value), 'cell'), P(escape(note), 'cell_m')])
        add(table(rows, [W * .34, W * .2, W * .46]))
        if comp['decisions']:
            add(P('Care plans chosen by participants', 'h')); add(Bars(comp['decisions'], label_w=175, color=colors.HexColor('#3f8f6b')))
        if comp['pauses']:
            add(P('Where unfinished rounds paused', 'h')); add(Bars(comp['pauses'], label_w=175, color=GOLD))

    # ---- Survey -----------------------------------------------------------
    if kind in ('full', 'feedback'):
        add(Spacer(1, 14)); add(CondPageBreak(220))
        add(P('02 · SURVEY' if kind == 'full' else 'SURVEY', 'eyebrow')); add(P('What participants told us', 'section'))
        add(P('After completing a case, participants were invited to rate the workflow and answer four short questions. Responses are voluntary.', 'small'))
        if not sv['n']:
            add(none('No survey responses recorded for this cohort yet.'))
        else:
            dist = [dict(r, color=GOLD) for r in sv['distribution']]
            left = [P('RATING DISTRIBUTION', 'eyebrow'), Bars(dist, width=W / 2 - 8, label_w=55, color=GOLD)]
            right = [P('RATING BY ROLE', 'eyebrow')]
            if sv['by_role']:
                rr = [th('Role', 'n', 'Average')] + [[P(escape(r['label']), 'cell'), P(str(r['n']), 'cell'), P(f"{r['average']:.1f} / 5", 'cell_b')] for r in sv['by_role']]
                right.append(table(rr, [(W / 2 - 8) * .56, (W / 2 - 8) * .2, (W / 2 - 8) * .24], zebra=False))
            pair = Table([[left, right]], colWidths=[W / 2, W / 2], hAlign='LEFT')
            pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
            add(pair)
            add(P('Most useful part of the platform', 'h')); add(Bars(sv['most_useful'], label_w=200))
            add(P('Factors that would most influence adoption', 'h'))
            add(P('Participants could choose up to three, so percentages can add up to more than 100%.', 'small'))
            add(Bars(sv['factors'], label_w=200, color=colors.HexColor('#2f6f8a')))
            add(P('Next step participants asked for', 'h')); add(Bars(sv['intents'], label_w=200, color=colors.HexColor('#3f8f6b')))
            add(CondPageBreak(160))
            add(P('Summary of written feedback', 'h'))
            if sv['themes']:
                add(P(f"{len(sv['written'])} of {sv['n']} responses included a written comment. Comments are grouped into themes by the words they use; one comment can touch several themes.", 'small'))
                rows = [th('Theme', 'Comments', 'Representative comment')]
                for th_ in sv['themes']:
                    q = th_['quote']
                    rows.append([P(escape(th_['theme']), 'cell_b'), P(f"{th_['n']} ({th_['pct']}%)", 'cell'),
                                 P(f"“{escape(q['text'][:260])}{'…' if len(q['text']) > 260 else ''}”<br/><font color='#607b77' size='6.6'>{escape(q['who'])} · {escape(q['role'])} · {q['rating']}/5</font>", 'cell')])
                add(table(rows, [W * .26, W * .13, W * .61]))
            elif sv['written']:
                add(P('Written comments did not match the predefined themes; see the full list below.', 'small'))
            else:
                add(none('No written comments were left.'))
            if sv['written']:
                add(P('All written comments', 'h'))
                for item in sv['written']:
                    org = f" · {escape(item['organisation'])}" if item['organisation'] else ''
                    block = Table([[[P(f"“{escape(item['text'])}”", 'quote'),
                                     P(f"{escape(item['who'])} · {escape(item['role'])}{org} · rated {item['rating']}/5 · {when(item['date'])} · Next step: {escape(item['intent'])}", 'small')]]],
                                  colWidths=[W])
                    block.setStyle(TableStyle([('LINEBEFORE', (0, 0), (0, -1), 2, GOLD), ('LEFTPADDING', (0, 0), (-1, -1), 10),
                                               ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 2)]))
                    add(KeepTogether([block, Spacer(1, 5)]))

    # ---- Participant register ---------------------------------------------
    if kind in ('full', 'participants'):
        add(Spacer(1, 14)); add(CondPageBreak(160))
        add(P('03 · REGISTER' if kind == 'full' else 'REGISTER', 'eyebrow')); add(P('Participant register', 'section'))
        add(P(('Participants are listed by name with contact details. Internal use only.' if named else
               'Participants are shown as pseudonyms (P-01 is the earliest registration in this report). Names, emails and phone numbers are removed; organisation and role are as self-reported.'), 'small'))
        if not d['register']:
            add(none('No participants registered in this cohort yet.'))
        else:
            rows = [th('Participant', 'Organisation / role', 'Source', 'Joined', 'Done', 'Best', 'Rating', 'Most useful / next step')]
            for r in d['register']:
                contact = ''.join(f"<br/><font color='#607b77' size='6.4'>{escape(x)}</font>" for x in (r['email'], r['whatsapp']) if x)
                rows.append([P(f"<b>{escape(r['who'])}</b>{contact}", 'cell'), P(f"{t(r['organisation'])}<br/><font color='#607b77' size='6.4'>{t(r['role'])}</font>", 'cell'),
                             P(t(r['source']), 'cell'), P(when(r['registered']), 'cell'), P(f"{r['completed']}/{r['rounds']}", 'cell'),
                             P(f"{r['best']}%", 'cell'), P(f"{r['rating']}/5" if r['rating'] else '—', 'cell_b'),
                             P(f"{t(r['useful'])}<br/><font color='#607b77' size='6.4'>{t(r['intent'], '')}</font>", 'cell')])
            add(table(rows, [W * .19, W * .19, W * .11, W * .1, W * .065, W * .07, W * .075, W * .2]))

    # ---- Interest ----------------------------------------------------------
    if kind in ('full', 'interest'):
        add(Spacer(1, 14)); add(CondPageBreak(220))
        add(P('04 · INTEREST' if kind == 'full' else 'INTEREST', 'eyebrow')); add(P('Interest and pipeline', 'section'))
        add(P('Enquiries from the website contact form, the pilot / interest form and the post-walkthrough survey. An enquiry is a request to talk, not a commitment.', 'small'))
        if not it['n']:
            add(none('No enquiries recorded for this cohort yet.'))
        else:
            left = [P('WHAT THEY ASKED FOR', 'eyebrow'), Bars(it['by_type'], width=W / 2 - 8, label_w=120)]
            right = [P('PIPELINE STAGE', 'eyebrow'), Bars(it['pipeline'], width=W / 2 - 8, label_w=100, color=colors.HexColor('#3f8f6b'))]
            pair = Table([[left, right]], colWidths=[W / 2, W / 2], hAlign='LEFT')
            pair.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
            add(pair)
            if it['organisations']:
                add(P('Organisations that enquired', 'h')); add(P(', '.join(escape(o) for o in it['organisations']), 'body'))
            add(P('Enquiry log', 'h'))
            add(P('Enquirers are listed by name with contact details. Internal use only.' if named else
                  'Enquirers are shown as E-01, E-02…; names, emails and phone numbers are removed. Messages are as written by the enquirer.', 'small'))
            rows = [th('Enquirer', 'Organisation / role', 'Interest', 'Stage / next action', 'Message')]
            for r in it['rows']:
                contact = ''.join(f"<br/><font color='#607b77' size='6.4'>{escape(x)}</font>" for x in (r['email'], r['whatsapp']) if x)
                tried = "<br/><font color='#147c70' size='6.4'>Used the workspace</font>" if r['tried'] else ''
                nxt = f"<br/><font color='#607b77' size='6.4'>{escape(r['next_action'])}{(' · ' + when(r['next_date'])) if r['next_date'] else ''}</font>" if r['next_action'] else ''
                msg = r['message'][:420] + ('…' if len(r['message']) > 420 else '')
                rows.append([P(f"<b>{escape(r['who'])}</b>{contact}<br/><font color='#607b77' size='6.4'>{when(r['date'])} · {escape(r['origin'])}</font>", 'cell'),
                             P(f"{t(r['organisation'])}<br/><font color='#607b77' size='6.4'>{t(r['role'], '')}</font>{tried}", 'cell'),
                             P(escape(r['interest']), 'cell_b'), P(f"{escape(r['stage'])}{nxt}", 'cell'), P(t(msg), 'cell')])
            add(table(rows, [W * .19, W * .19, W * .16, W * .15, W * .31]))

    # ---- Method ------------------------------------------------------------
    add(Spacer(1, 16)); add(CondPageBreak(170))
    add(P('METHOD', 'eyebrow')); add(P('How these figures were collected', 'section'))
    for line in [
        'Source: activity recorded automatically in the VanaraOncoScan pilot workspace. At registration, every participant agreed to the use of their registration details, walkthrough activity and feedback for MVP evaluation. Reviewers invited through an organisation access link agreed to the same on entry.',
        'Landing visits are browser sessions with a 30-minute inactivity boundary; staff visits are excluded. A round is one case taken through the workspace; it is completed when a care plan is recorded and the case report is downloaded (or the quality report, when an image fails the quality check).',
        'Ratings use a 1–5 scale for perceived usefulness of the workflow. Written comments are grouped by keyword themes; this is a transparent summary aid, not a statistical analysis.',
        'Limitations: participants are self-selected; the preview uses sample patients and images; ratings measure perceived usefulness, not diagnostic accuracy. With small numbers, read percentages together with the counts shown.',
        f"Integrity: this report was generated directly from the database on {when(d['generated'], '%d %b %Y at %H:%M')}. Reference {d['reference']}; data fingerprint (SHA-256) {d['fingerprint']}.",
    ]:
        add(P(f'<font color="#147c70"><b>•</b></font>&nbsp;&nbsp;{escape(line)}', 'bullet'))

    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=70, bottomMargin=62,
                            title=f'VanaraOncoScan · {title}', author='Vanara Multi-Ventures', subject='Validation evidence')
    meta = {'band': band, 'reference': d['reference'], 'named': named, 'fingerprint': d['fingerprint'],
            'generated': when(d['generated'], '%d %b %Y, %H:%M')}
    doc.build(story, canvasmaker=lambda *a, **kw: EvidenceCanvas(*a, meta=meta, **kw))
    return out.getvalue()
