"""Draw the final workflow without changing any historical figure."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[2]
out = root / "paper/figures/final_v3/fig01_workflow.png"
out.parent.mkdir(parents=True, exist_ok=True)
im = Image.new("RGB", (2200, 800), "white")
draw = ImageDraw.Draw(im)
font = ImageFont.truetype(r"C:\Windows\Fonts\simsun.ttc", 40)
small = ImageFont.truetype(r"C:\Windows\Fonts\simsun.ttc", 34)
labels = [
    ["48条原始记录", "保留44条非起搏记录"], ["标签映射与滤波", "253点单导联窗口"],
    ["43患者独立分区", "31 / 6 / 6 患者组"], ["训练侧统计参数", "归一化与损失权重"],
    ["报告与教学展示", "真实推理及来源导出"], ["逐类指标与错误", "真实模型积分梯度"],
    ["验证选型与冻结", "旧测试探索性复用"], ["原工件复验另存", "新增4方案×3种子"],
]
boxes=[]
for i, lines in enumerate(labels):
    col=i%4; row=i//4;x=55+col*550;y=90+row*340
    box=(x,y,x+440,y+190);boxes.append(box)
    draw.rounded_rectangle(box,radius=10,outline="#71869a",width=3,fill="#f3f6f9")
    for j,t in enumerate(lines):
        bb=draw.textbbox((0,0),t,font=font);draw.text((x+(440-bb[2]+bb[0])/2,y+43+j*65),t,font=font,fill="#243647")
def arrow(start,end):
    draw.line((start,end),fill="#60778c",width=4)
    x,y=end;sx,sy=start
    if y==sy: pts=[(x,y),(x-13 if x>sx else x+13,y-9),(x-13 if x>sx else x+13,y+9)]
    else: pts=[(x,y),(x-9,y-13),(x+9,y-13)]
    draw.polygon(pts,fill="#60778c")
for a,b in [(0,1),(1,2),(2,3)]:arrow((boxes[a][2],185),(boxes[b][0],185))
arrow((1925,280),(1925,430))
for a,b in [(7,6),(6,5),(5,4)]:arrow((boxes[a][0],525),(boxes[b][2],525))
note="原始实验与六个生产模型独立保留；新增训练、验证选型和一次测试阶段单独记录"
bb=draw.textbbox((0,0),note,font=small);draw.text(((2200-bb[2])/2,710),note,font=small,fill="#4b6071")
im.save(out)
print(out)
