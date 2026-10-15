"""Render the simplified behavior flow."""
from pathlib import Path
from math import atan2, cos, sin
from reportlab.pdfgen import canvas

root = Path(__file__).resolve().parents[1]
out = root / 'output/pdf/tentacle-state-diagram.pdf'
out.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(out), pagesize=(1000,650))
c.setTitle('Tentacle behavior flow')

def text(x,y,s,size=13):
    c.setFont('Helvetica',size)
    c.drawCentredString(x,y,s)

def box(x,y,w,h,lines):
    c.setLineWidth(1.2)
    c.rect(x,y,w,h)
    for i,s in enumerate(lines):
        text(x+w/2,y+h/2+(len(lines)-1)*10-i*20,s)

def arrow(points):
    p=c.beginPath();p.moveTo(*points[0])
    for q in points[1:]:p.lineTo(*q)
    c.drawPath(p)
    x,y=points[-1];px,py=points[-2];a=atan2(y-py,x-px)
    p=c.beginPath();p.moveTo(x,y)
    p.lineTo(x-7*cos(a-.4),y-7*sin(a-.4))
    p.lineTo(x-7*cos(a+.4),y-7*sin(a+.4));p.close()
    c.drawPath(p,fill=1)

box(350,555,300,60,['START','Next behavior = 1'])
arrow([(500,555),(500,515)])
box(350,445,300,70,['SENSOR DETECTS OBJECT','Closer than 20 cm'])
arrow([(500,445),(500,405)])
box(350,345,300,60,['CHECK NEXT BEHAVIOR','1, 2 or 3'])
arrow([(500,345),(500,320),(190,320),(190,280)])
arrow([(500,345),(500,280)])
arrow([(500,320),(810,320),(810,280)])
c.circle(500,320,2,fill=1)
for x,n in [(190,1),(500,2),(810,3)]:text(x+35,295,str(n))
box(60,150,260,130,['BEHAVIOR 1','Roar for 1.4 seconds','Then pull left','and return'])
box(370,150,260,130,['BEHAVIOR 2','Roar for 2.1 seconds','Then pull right','and return'])
box(680,150,260,130,['BEHAVIOR 3','Roar for 2.8 seconds','Then alternate left/right tugs','for 3 cycles'])
arrow([(190,150),(190,120),(500,120),(500,95)])
arrow([(500,150),(500,95)])
arrow([(810,150),(810,120),(500,120)])
c.circle(500,120,2,fill=1)
box(325,25,350,70,['AFTER THE FULL BEHAVIOR FINISHES','Completed count + 1','Next behavior: 1 -> 2 -> 3 -> 1'])
arrow([(325,60),(25,60),(25,480),(350,480)])
text(175,495,'Wait for next detection',11)
c.showPage();c.save()
print(out)
