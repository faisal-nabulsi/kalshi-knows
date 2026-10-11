import qrcode
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

BG=RGBColor(0x0A,0x0A,0x0B); BONE=RGBColor(0xED,0xE8,0xDF); OR=RGBColor(0xFF,0x4D,0x1A); DIM=RGBColor(0x8F,0x8B,0x84)
DISP="DIN Condensed"; BODY="Helvetica Neue"
C="results/charts/"
qrcode.make("https://kalshi-knows.pages.dev", box_size=12, border=2).save("slides/qr.png")

p=Presentation(); p.slide_width=Inches(13.333); p.slide_height=Inches(7.5)
blank=p.slide_layouts[6]

def slide(notes, tag=None):
    s=p.slides.add_slide(blank)
    s.background.fill.solid(); s.background.fill.fore_color.rgb=BG
    s.notes_slide.notes_text_frame.text=notes
    if tag: text(s,tag,0.6,0.35,6,0.4,14,OR,font=BODY,bold=True)
    return s

def text(s,t,x,y,w,h,size,color=BONE,font=BODY,bold=False,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); tf=tb.text_frame; tf.word_wrap=True
    tf.vertical_anchor=anchor
    for m in ("margin_left","margin_right","margin_top","margin_bottom"): setattr(tf,m,0)
    lines=t if isinstance(t,list) else [t]
    for i,l in enumerate(lines):
        para=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        para.alignment=align
        r=para.add_run(); r.text=l; f=r.font; f.size=Pt(size); f.color.rgb=color; f.name=font; f.bold=bold
    return tb

def title(s,t,y=0.8,size=54): text(s,t,0.6,y,12.1,1.2,size,BONE,DISP,True)
def rule(s,x,y,w=1.2):
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(0.07)); r.fill.solid(); r.fill.fore_color.rgb=OR; r.line.fill.background()
def qr(s,x=11.2,y=5.0,sz=1.7):
    s.shapes.add_picture("slides/qr.png",Inches(x),Inches(y),Inches(sz),Inches(sz))
    text(s,"kalshi-knows.pages.dev",x-0.5,y+sz+0.05,sz+1,0.3,12,DIM,align=PP_ALIGN.CENTER)
def pic(s,f,x,y,w=None,h=None):
    s.shapes.add_picture(C+f,Inches(x),Inches(y),Inches(w) if w else None,Inches(h) if h else None)
def big(s,num,label,x,y,w,size=80,color=OR):
    text(s,num,x,y,w,size/72*1.1,size,color,DISP,True)
    text(s,label,x,y+size/72*1.1,w,0.9,18,BONE)

# 1 title
s=slide("Prediction markets know things before you do. We built the layer that reads them.")
text(s,"KALSHI",0.6,0.9,9,2.2,150,BONE,DISP,True)
text(s,"KNOWS",0.6,2.6,9,2.2,150,OR,DISP,True)
text(s,"The intelligence layer on top of prediction markets",0.6,5.5,9,0.5,24,BONE)
text(s,"Faisal Nabulsi  ·  Kevin Huang  ·  Dugar",0.6,6.3,9,0.4,18,DIM)
qr(s,10.6,3.9,2.1)

# 2 problem
s=slide("Kalshi's price moves about 7 seconds after a play. Your stream shows it 48 to 62 seconds after. Anyone live-betting off a stream is trading against people who already know, and every streaming fan gets spoiled by group chats.","THE PROBLEM")
title(s,"KALSHI MOVES IN 7 SECONDS. YOUR STREAM TAKES 48 TO 62.",0.7,44)
pic(s,"a_kalshi_beats_your_stream.png",0.6,2.0,h=4.6)
big(s,"7 s","Kalshi price after the play",9.4,2.4,3.4,96)
big(s,"48–62 s","Peacock to NFL+ (antenna 19, cable 38, YouTube TV 53)",9.4,4.6,3.6,60,BONE)

# 3 who
s=slide("We don't compete with Kalshi. We're the analytics layer on top, starting with retail traders and fans.","WHO IT'S FOR")
title(s,"THE ANALYTICS LAYER ON TOP OF KALSHI",0.7,48)
cols=[("RETAIL","Streaming fans and prediction-market traders","Spoiler alerts, \"market already moved\" warnings"),
      ("QUANTS","Latency and info-flow data","Who learns what, and when"),
      ("EXCHANGES","Regulators: market-integrity monitoring","See when a price moved before the news")]
for i,(a,b,c) in enumerate(cols):
    x=0.6+i*4.15
    rule(s,x,2.5,3.6); text(s,a,x,2.75,3.8,0.9,40,OR,DISP,True)
    text(s,b,x,3.75,3.7,1.2,24,BONE,bold=True); text(s,c,x,5.0,3.7,1.2,18,DIM)

# 4 demo
s=slide("Here's today. Every call is timestamped and graded against ESPN, misses included. When we named the play today, we were right 4 of 7, and the misses are on screen. Then the Auto page: the same signals drive an agent that places orders on Kalshi's demo exchange, play money, and it works on any market. Also point at the Kalshi vs Polymarket panel under the game tiles: we watch both venues; Kalshi moves first. (Backup: video/kalshi-knows-demo.mp4, or the ledger backup slide.)","LIVE DEMO")
text(s,"LIVE",0.6,1.4,12,3.2,260,OR,DISP,True)
text(s,"Live board  →  Receipts  →  Auto page",0.6,4.9,12,0.6,32,BONE)
text(s,"Today: 30 alerts · named calls 4 of 7 right (misses shown) · Steelers TD called 32 s before ESPN's feed",0.6,5.7,11,0.8,20,DIM)
text(s,"kalshi-knows.pages.dev/?present=1",0.6,6.5,8,0.4,16,DIM)

# 5 how
s=slide("Two-stage model. The 28-season pretraining is the secret sauce: the model beats a smart fan by about 11 points, and without the pretraining it drops to 70%. We audited our own labels, found 15% were wrong, fixed them.","HOW IT WORKS")
title(s,"TWO-STAGE MODEL, 28 SEASONS OF NFL PLAYS",0.7,48)
boxes=["Kalshi public\norder book","Jump\ndetector","Play model","Push + live site\n+ auto-bettor"]
sub=["","price move ≥ 0.08","pretrained on 28 seasons of NFL plays, fine-tuned on ~8,800 real Kalshi jumps",""]
for i,b in enumerate(boxes):
    x=0.6+i*3.15
    r=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(x),Inches(2.5),Inches(2.7),Inches(1.5))
    r.fill.background(); r.line.color.rgb=OR if i==2 else BONE; r.line.width=Pt(2.5 if i==2 else 1.5)
    tf=r.text_frame; tf.word_wrap=True; tf.vertical_anchor=MSO_ANCHOR.MIDDLE
    for j,l in enumerate(b.split("\n")):
        pr=tf.paragraphs[0] if j==0 else tf.add_paragraph(); pr.alignment=PP_ALIGN.CENTER
        rr=pr.add_run(); rr.text=l; rr.font.size=Pt(24); rr.font.name=DISP; rr.font.bold=True; rr.font.color.rgb=BONE
    if i<3: text(s,"→",x+2.72,2.95,0.4,0.6,30,OR,bold=True,align=PP_ALIGN.CENTER)
    text(s,sub[i],x,4.15,2.7,1.2,14,DIM,align=PP_ALIGN.CENTER)
big(s,"+11 pts","over a smart fan",0.6,5.1,4,64)
big(s,"15% → 3.3%","wrong labels, before vs after our audit",5.0,5.1,5,64,BONE)

# 6 results
s=slide("Tested on games it never saw, against a smart fan and against Claude. Always-'nothing' baseline is 47 to 50% on the audited labels. Named calls at 75%+ confidence were right 77 to 81% of the time. Pre-registered test on today's early games: named calls 8 of 9 (small sample, wide interval). Claude Opus 5.5 head-to-head: 77.3% vs 76.0%, a statistical tie on accuracy, clearly better calibrated, 7 ms per call.","RESULTS")
title(s,"74–75% ON GAMES IT NEVER SAW",0.7,48)
pic(s,"h_model_vs_smart_fan.png",0.6,1.9,h=4.2)
rows=[("Smart fan","63%",BONE),("Kalshi Knows","74–75%",OR),("Always \"nothing\"","47–50%",DIM)]
for i,(a,b,c) in enumerate(rows):
    y=2.0+i*0.8
    text(s,a,8.6,y+0.12,2.6,0.6,20,c); text(s,b,11.0,y,2.0,0.7,40,c,DISP,True)
text(s,["Named at 75%+: right ~80%","vs Claude Opus 5.5: ties on accuracy (77 vs 76%), better calibrated, 7 ms","Pre-registered test on today's games: named calls 8 of 9"],8.6,4.6,4.3,2.2,17,BONE)

# 7 taught
s=slide("We tried hard to find a flaw. The market digests plays in seconds; the only edge is speed, and that's what we sell.","WHAT THE MARKET TAUGHT US")
title(s,"WE TRIED TO BREAK IT. THE MARKET HELD.",0.7,48)
big(s,"1,255","trading rules tested",0.6,2.0,3.8,80,BONE)
big(s,"11","passed the stats",4.5,2.0,3.2,80,BONE)
big(s,"0","survived our skeptics",7.7,2.0,3.8,80)
pic(s,"g_dutch_book_funnel.png",0.6,4.2,h=2.9)
text(s,["Weather, injuries, spreads: already priced in","Dutch Book: ~100k markets, 16 arbs before fees, 0 after","The edge is speed"],6.4,4.5,6.3,2.4,22,BONE)

# 8 business
s=slide("Retail is the wedge, B2B data is the business. Proof it scales past NFL: the cross-market model trained on 4.36M settled Kalshi markets beats the raw market price on an unseen month (2.7% better Brier). Comps: Action Network PRO $24.99/mo, OddsJam $199+/mo.","BUSINESS")
title(s,"RETAIL IS THE WEDGE. DATA IS THE BUSINESS.",0.7,48)
tiers=[("FREE","$0","Spoiler alerts + Spoiler Shield + Receipts"),
       ("PRO","~$15/mo","Auto-bet rules, \"market already moved\" warnings, all markets"),
       ("B2B","Info-flow API","Integrity monitoring. Princeton rankings moved ~6.8 h before the official release")]
for i,(a,b,c) in enumerate(tiers):
    x=0.6+i*4.15
    rule(s,x,2.4,3.6); text(s,a,x,2.6,3.6,0.6,22,OR,BODY,True); text(s,b,x,3.2,3.8,1.1,44,BONE,DISP,True); text(s,c,x,4.4,3.6,1.3,18,DIM)
text(s,"Comps: Action Network PRO $24.99/mo · OddsJam $199+/mo",0.6,5.8,8,0.4,16,DIM)
text(s,"Works beyond NFL: trained on 4.36M settled Kalshi markets, beats the raw price on an unseen month by 2.7% (Brier)",0.6,6.3,12,0.4,18,BONE)

# 9 close
s=slide("Kalshi knows. Now you do too.")
text(s,"KALSHI KNOWS.",0.6,1.2,9.5,1.6,100,BONE,DISP,True)
text(s,"NOW YOU DO TOO.",0.6,2.8,9.5,1.6,100,OR,DISP,True)
text(s,"Public data only. No real money.",0.6,5.8,9,0.5,24,BONE)
text(s,"Faisal Nabulsi  ·  Kevin Huang  ·  Dugar",0.6,6.4,9,0.4,18,DIM)
qr(s,10.6,3.9,2.1)

# backups
def backup(n,t,f,note,h=5.2,x=None):
    s=slide(note,"BACKUP")
    title(s,t,0.7,44); 
    pic(s,f,0.6 if x is None else x,1.8,h=h)
backup(1,"MODEL LEADERBOARD","b_model_leaderboard.png","Backup: all model families compared on the same plays (STATS.md section 0). Smart fan 62.8%, XGBoost without pretraining 70.0%, audited-label model 73.8% CV and 75.0% temporal.")
backup(2,"ACCURACY VS CONFIDENCE","e_accuracy_vs_confidence.png","Backup: named calls at 75%+ confidence were right 76.6% (temporal, 94 calls) to 80.5% (CV, 466 calls) of the time.")
backup(3,"DEMO EXCHANGE LEDGER (PLAY MONEY)","i_demo_ledger.png","Backup: real signed order on Kalshi's demo exchange at 2:05pm, bought 1 YES '49ers win' at $0.39, fee $0.0167. Demo only, no real money. Refresh with results/export_demo.py.",h=5.3)
p.save("slides/kalshi-knows-draft.pptx")
