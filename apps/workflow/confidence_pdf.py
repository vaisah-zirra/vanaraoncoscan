from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Flowable, Paragraph


class ConfidenceCard(Flowable):
    """Clockwise percentage arc, with an exact remainder and readable text equivalent."""
    def __init__(self, display, width=202):
        super().__init__()
        self.display=display; self.width=width; self.height=132

    def text(self,text,x,y,width,size=8,bold=False,color='#183d3d'):
        style=ParagraphStyle('card',fontName='Report-Bold' if bold else 'Report',fontSize=size,leading=size+3,textColor=colors.HexColor(color))
        p=Paragraph(escape(text),style); _,height=p.wrap(width,100)
        p.drawOn(self.canv,x,y-height)
        return height

    def draw(self):
        c=self.canv; d=self.display
        tone=colors.HexColor(d['color'])
        # Quiet white surface, consistent inset, and two distinct information zones.
        c.setFillColor(colors.HexColor('#eef2f0'))
        c.roundRect(0,-2,self.width,self.height,10,fill=1,stroke=0)
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor('#dfe7e3')); c.setLineWidth(.6)
        c.roundRect(0,0,self.width,self.height,10,fill=1,stroke=1)
        self.text('AI ASSESSMENT',16,119,self.width-32,6.5,True,color='#758680')
        cx,cy,r=43,81,22
        c.setStrokeColor(colors.HexColor('#edf0ef')); c.setLineWidth(4)
        c.circle(cx,cy,r,fill=0,stroke=1)
        if d['has_score']:
            c.setStrokeColor(tone); c.setLineCap(0)
            c.arc(cx-r,cy-r,cx+r,cy+r,startAng=90,extent=-360*d['score']/100)
        c.setFillColor(colors.HexColor('#243f37')); c.setFont('Report-Bold',14)
        c.drawCentredString(cx,cy-5,str(d['score'])+'%' if d['has_score'] else 'N/A')
        self.text('Model confidence',80,95,self.width-96,8.5,True,color='#243f37')
        self.text('VOS-BUS v0.9' if d['has_score'] else 'Not available',80,73,self.width-96,7,color='#758680')
        c.setLineWidth(.5); c.setStrokeColor(colors.HexColor('#e8eeeb'))
        c.line(16,48,self.width-16,48)
        self.text(d['label'],16,39,self.width-32,10,True,color=d['color'])
