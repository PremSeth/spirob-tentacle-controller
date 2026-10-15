"""Render the controller state diagram with ReportLab."""
from pathlib import Path
from math import atan2, cos, sin
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black, white

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf/tentacle-state-diagram.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
c = canvas.Canvas(str(OUT), pagesize=(1100,1120))
c.setTitle('Tentacle controller states')

def label(x,y,s,size=11):
    c.setFont('Helvetica',size)
    c.drawCentredString(x,y,s)

def box(x,y,w,h,lines):
    c.setLineWidth(1.2)
    c.rect(x,y,w,h)
    for i,s in enumerate(lines):
        label(x+w/2,y+h/2+(len(lines)-1)*8-i*16,s)

def arrow(points):
    c.setLineWidth(1.2)
    p=c.beginPath(); p.moveTo(*points[0])
    for q in points[1:]: p.lineTo(*q)
    c.drawPath(p)
    x,y=points[-1]; px,py=points[-2]; a=atan2(y-py,x-px)
    p=c.beginPath();p.moveTo(x,y)
    p.lineTo(x-7*cos(a-.4),y-7*sin(a-.4))
    p.lineTo(x-7*cos(a+.4),y-7*sin(a+.4));p.close()
    c.drawPath(p,fill=1)

def down(x,y1,y2): arrow([(x,y1),(x,y2)])

box(400,1035,300,55,['BOOT / DISARMED','Motors off; sound off'])
down(550,1035,995);label(585,1010,'ARM')
box(400,945,300,50,['ARMED / IDLE'])
down(550,945,910);label(585,923,'AUTO')
box(400,850,300,60,['completed = 0; next behavior = 1','Enable automatic detection'])
down(550,850,815)
box(400,745,300,70,['SAMPLE HC-SR04 DISTANCE','At least 70 ms between readings','2 <= distance < 20 cm?'])
arrow([(400,780),(300,780),(300,700),(400,700)])
box(400,675,300,50,['No: reset near-reading count'])
arrow([(700,700),(755,700),(755,780),(700,780)])
label(350,788,'No')
arrow([(550,745),(550,735),(160,735),(160,655)])
label(195,712,'Yes')
box(40,595,240,60,['Increment near-reading count','Three consecutive near readings?'])
arrow([(280,625),(330,625),(330,810),(400,810)])
label(307,641,'No')
arrow([(160,595),(160,565),(550,565),(550,535)])
label(182,576,'Yes')
box(400,475,300,60,['RUN next behavior','Ignore sensor triggers until finished','completed stays unchanged'])
arrow([(550,475),(550,455),(210,455),(210,425)])
down(550,475,425)
arrow([(550,455),(890,455),(890,425)])
for x in [210,550,890]:
    c.circle(x,455,2,fill=1)
box(70,375,280,50,['BEHAVIOR 1: ROAR 1','1.4 s; motors off until roar finishes'])
box(410,375,280,50,['BEHAVIOR 2: ROAR 2','2.1 s; motors off until roar finishes'])
box(750,375,280,50,['BEHAVIOR 3: ROAR 3','2.8 s; motors off until roar finishes'])
for x in [210,550,890]:down(x,375,350)
box(70,290,280,60,['LEFT PULL','A tug 500 ms + B release 125 ms','Stop each motor at its own deadline'])
box(410,290,280,60,['RIGHT PULL','B tug 500 ms + A release 125 ms','Stop each motor at its own deadline'])
box(750,290,280,60,['REPEAT 3 CYCLES','A tug 250 ms; B off','80 ms pause'])
for x in [210,550]:down(x,290,260)
box(70,190,280,70,['RESET AFTER LEFT','500 ms pause (two 250 ms stages)','B tug 500 ms + A release 125 ms','250 ms final pause'])
box(410,190,280,70,['RESET AFTER RIGHT','500 ms pause (two 250 ms stages)','A tug 500 ms + B release 125 ms','250 ms final pause'])
down(890,290,270)
box(750,210,280,60,['A release 50 ms + B tug 250 ms','Then 80 ms pause'])
down(890,210,190)
box(750,130,280,60,['B release 50 ms; A off','80 ms pause; repeat until 3 cycles'])
arrow([(1030,160),(1050,160),(1050,320),(1030,320)])
label(1057,243,'',10)
arrow([(210,190),(210,105),(550,105),(550,85)])
arrow([(550,190),(550,85)])
arrow([(890,130),(890,105),(550,105)])
c.circle(550,105,2,fill=1)
box(370,25,360,60,['FINISHED: completed += 1','next behavior = 1 -> 2 -> 3 -> 1','500 ms cooldown, then sample again'])
arrow([(370,55),(20,55),(20,830),(550,830),(550,815)])
box(790,965,270,105,['FROM ANY ACTIVE STATE','STOP: motors/sound off; AUTO off','DISARM / !: also disarm','Aborted behavior does not add a count','ARM + AUTO starts over'])
box(790,845,270,90,['EACH MOTOR MOVEMENT','PWM 50 -> 80; rise 100 ms (or shorter)','Stop at the specified elapsed time','PWM controls drive, not measured speed'])
for y in (700,735,780):
    c.setStrokeColor(white); c.setLineWidth(4); c.line(323,y,337,y)
    c.setStrokeColor(black); c.setLineWidth(1.2)
    p=c.beginPath();p.moveTo(323,y);p.curveTo(323,y+10,337,y+10,337,y)
    c.drawPath(p)
for x,n in [(210,1),(550,2),(890,3)]: label(x+35,435,f'next = {n}',10)
c.showPage();c.save()
print(OUT)
