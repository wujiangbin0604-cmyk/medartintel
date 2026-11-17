"""Deterministic, high-resolution publication charts from saved real data."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,csv,math
import numpy as np
P=Path(__file__).resolve().parents[1]; ROOT=P.parent; OUT=P/'figures/v2'
OUT.mkdir(exist_ok=True)
COL=['#267B88','#D68D00','#C83C49','#8356A8']; MODEL=['#4477AA','#EE7733','#228833']
FONT=r'C:\Windows\Fonts\simsun.ttc'; BOLD=r'C:\Windows\Fonts\simhei.ttf'; FONT_MIN=0
def font(n=48,b=False):return ImageFont.truetype(BOLD if b else FONT,max(n,FONT_MIN))
def txt(d,xy,s,n=48,fill='#111111',anchor=None,b=False):d.text(xy,str(s),font=font(n,b),fill=fill,anchor=anchor)
def save(im,name):im.save(OUT/name,dpi=(400,400))
def canvas(h=1600):
    im=Image.new('RGB',(3000,h),'white');return im,ImageDraw.Draw(im)
def table(path):return list(csv.DictReader((ROOT/path).open(encoding='utf-8-sig')))
def load(path):return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
def axis(d,box,title,ymax=1,yticks=5):
    x,y,w,h=box; txt(d,(x+w/2,y-80),title,54,anchor='mm',b=True)
    for k in range(yticks+1):
        v=ymax*k/yticks; yy=y+h-h*k/yticks;d.line((x,yy,x+w,yy),fill='#DDE3E7',width=2)
        label=f'{v:.1f}' if ymax<=1 else f'{v:g}'
        txt(d,(x-20,yy),label,40,anchor='rm')
    d.line((x,y,x,y+h,x+w,y+h),fill='#333333',width=3)
def bars(d,box,labels,series,ymax=1,colors=None,valuefmt='.3f'):
    x,y,w,h=box; n=len(labels); m=len(series); gw=w/n; bw=gw*.75/m
    for i,label in enumerate(labels):
        txt(d,(x+gw*(i+.5),y+h+38),label,42,anchor='mt')
        for j,vals in enumerate(series):
            v=vals[i]; xx=x+gw*i+gw*.125+j*bw; yy=y+h-h*v/ymax
            color=(colors or MODEL)[j if len(series)>1 else i%len(colors or MODEL)]
            d.rectangle((xx,yy,xx+bw*.9,y+h),fill=color)
            if valuefmt is not None:txt(d,(xx+bw*.45,yy-12),format(v,valuefmt),38,anchor='mb')
def legend(d,items,y=1450):
    gap=3000/len(items)
    for i,(name,c) in enumerate(items):
        x=gap*i+90; d.rectangle((x,y,x+50,y+30),fill=c);txt(d,(x+70,y-10),name,43)
def box(d,rect,lines):
    d.rounded_rectangle(rect,radius=10,fill='#F2F5F7',outline='#506777',width=4)
    x,y,r,b=rect; step=66; start=(y+b-step*(len(lines)-1))/2
    for i,s in enumerate(lines):txt(d,((x+r)/2,start+i*step),s,48,anchor='mm')
def arrow(d,p,q,label=None):
    d.line((*p,*q),fill='#506777',width=6)
    dx=q[0]-p[0];dy=q[1]-p[1];a=math.atan2(dy,dx)
    pts=[q,(q[0]-26*math.cos(a-.5),q[1]-26*math.sin(a-.5)),(q[0]-26*math.cos(a+.5),q[1]-26*math.sin(a+.5))]
    d.polygon(pts,fill='#506777')
    if label:txt(d,((p[0]+q[0])/2,(p[1]+q[1])/2-30),label,38,anchor='mm')

def diagrams():
    im,d=canvas(1200)
    labels=[['读取48条记录','剔除4条起搏记录'],['显式标签映射','N/V 与 N/S/V/F'],['连续滤波与截窗','360 Hz · 253点'],['受试者独立分区','201/202合并'],['仅训练侧拟合','归一化与类别权重'],['训练三种模型','验证集选择检查点'],['固定测试与回顾','分组CV/错误分析'],['保存模型与结果','Web交互式展示']]
    for i,ls in enumerate(labels):
        row=i//4;col=i%4 if row==0 else 3-i%4;x=80+col*745;y=100+row*650
        box(d,(x,y,x+600,y+290),ls)
        if i<3:arrow(d,(x+600,y+145),(x+725,y+145))
        elif i==3:arrow(d,(x+300,y+290),(x+300,750))
        elif i<7:arrow(d,(x,y+145),(x-145,y+145))
    txt(d,(1500,1120),'固定测试已有查看历史；本轮只复核，不重新训练',46,anchor='mm')
    save(im,'fig01_workflow.png')
    im,d=canvas(1000)
    ls=[['输入','1 × 253'],['Conv1 + ReLU','16 × 253','MaxPool →126'],['Conv2 + ReLU','32 × 126','MaxPool →63'],['Conv3 + ReLU','64 × 63','平均池化 →1'],['Linear 64→K','输出logits','K = 2 或 4']]
    for i,xs in enumerate(ls):
        x=50+i*600;box(d,(x,170,x+490,640),xs)
        if i<4:arrow(d,(x+490,405),(x+585,405))
    txt(d,(1500,780),'卷积核 7 / 5 / 3，padding 3 / 2 / 1',50,anchor='mm')
    txt(d,(1500,880),'总参数 N/V 9058，四分类 9188；无额外注意力或循环分支',48,anchor='mm')
    save(im,'fig05_cnn.png')
    im,d=canvas(1600)
    box(d,(60,60,1050,340),['React / Umi 前端','Ant Design · ECharts'])
    box(d,(1850,60,2940,340),['FastAPI 接口','记录、推理、回放、研究结果'])
    arrow(d,(1080,145),(1810,145),'用户选拍与请求');arrow(d,(1810,285),(1080,285),'类别、分数与波形响应')
    box(d,(60,650,1050,940),['InferenceService / ECGStore','推理编排、窗口与预处理'])
    box(d,(1850,650,2940,940),['ModelRegistry','LR / RF / CNN工件推理'])
    arrow(d,(2300,350),(1040,640),'调用与结果返回');arrow(d,(1040,640),(2300,350))
    arrow(d,(1080,745),(1810,745),'标准化窗口与任务/模型')
    arrow(d,(1810,895),(1080,895),'类别、概率与工件信息')
    box(d,(60,1250,900,1510),['WFDB、元数据与划分','训练归一化与处理配置'])
    box(d,(1070,1250,1900,1510),['既有实验结果','指标、错误例、科研图'])
    box(d,(2080,1250,2940,1510),['模型工件与类别配置','LR保存的逐特征scaler'])
    arrow(d,(500,1240),(500,960),'读取');arrow(d,(2500,1240),(2500,960),'加载')
    txt(d,(1490,1160),'由FastAPI研究接口只读提供',40,anchor='mm')
    save(im,'fig12_architecture.png')

def statistics():
    global FONT_MIN
    FONT_MIN=56
    im,d=canvas(1450);boxes=[(220,180,1180,950),(1760,180,1040,950)]
    axis(d,boxes[0],'四分类有效心拍数',100000);axis(d,boxes[1],'至少含该类心拍的患者数',43,yticks=1)
    bars(d,boxes[0],['N','S','V','F'],[[89577,2761,6977,800]],100000,COL,'.0f')
    bars(d,boxes[1],['N','S','V','F'],[[43,31,32,16]],43,COL,'.0f')
    txt(d,(1500,1320),'44条记录对应43个受试者组；心拍数与独立患者数分别统计',47,anchor='mm')
    save(im,'fig04_support.png')
    j=load('paper/evidence/verified_metrics.json')
    im,d=canvas(1400)
    for k,(key,title) in enumerate([('accuracy','Accuracy'),('macro_f1','Macro-F1')]):
        b=(200+k*1500,180,1200,900);axis(d,b,title)
        vals=[[j['test_metrics'][task][m][key] for m in ['logistic_regression','random_forest','cnn_1d']] for task in ['nv','nsvf']]
        bars(d,b,['LR','RF','1D-CNN'],vals,colors=['#267B88','#C83C49'])
    legend(d,[('N/V固定测试','#267B88'),('N/S/V/F固定测试','#C83C49')],1250)
    save(im,'fig06_results.png')
    im,d=canvas(1200);b=(250,180,2450,730);axis(d,b,'少数类在相应分区的最大单患者份额（%）',100)
    bars(d,b,['训练F / 患者213','测试F / 患者208','验证S / 患者232'],[[88.077859,99.730458,98.005698]],100,[COL[3],COL[3],COL[1]],'.2f')
    txt(d,(1500,1100),'对应支持数：F训练411拍，F测试371拍，S验证1404拍',48,anchor='mm')
    save(im,'fig08_concentration.png')
    rows=table('results/classification/nsvf44_v1/diagnosis/weight_strategy_class_metrics.csv');st=['unweighted','sqrt_inverse','capped_inverse_10','full_inverse']
    im,d=canvas(1450)
    for k,c in enumerate(['S','F']):
        b=(200+1500*k,180,1200,900);axis(d,b,c+'类验证侧Precision与Recall')
        vals=[[float(next(r for r in rows if r['split']=='val' and r['strategy']==s and r['class']==c)[metric]) for s in st] for metric in ['precision','recall']]
        bars(d,b,['无权重','平方根','截断','完整逆频率'],vals,colors=['#4477AA','#EE7733'],valuefmt=None)
    legend(d,[('Precision','#4477AA'),('Recall','#EE7733')],1260)
    save(im,'fig09_weights.png')
    rows=table('results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_fold_metrics.csv')
    im,d=canvas(1350);b=(240,150,2500,880);axis(d,b,'四分类外折Macro-F1（仅train + validation患者）')
    for k,m in enumerate(['logistic_regression','random_forest','cnn_1d']):
        vals=[float(next(r for r in rows if r['model']==m and int(r['fold'])==f)['macro_f1_present_classes']) for f in range(1,6)]
        pts=[(b[0]+b[2]*(i+.5)/5,b[1]+b[3]*(1-v)) for i,v in enumerate(vals)]
        d.line(pts,fill=MODEL[k],width=7)
        for x,y in pts:d.ellipse((x-12,y-12,x+12,y+12),fill=MODEL[k])
    for i,n in enumerate([5,17,5,37,365]):txt(d,(b[0]+b[2]*(i+.5)/5,1080),f'折{i+1}  F={n}',44,anchor='mt')
    legend(d,[('LR',MODEL[0]),('RF',MODEL[1]),('1D-CNN',MODEL[2])],1220)
    save(im,'fig10_cv.png')

def error_cases():
    rows=table('results/classification/nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv')
    z=np.load(ROOT/'data/processed/mitdb44_nsvf_v1/test.npz',allow_pickle=False)
    im,d=canvas(3100);xx=z['relative_time_s']; index={s:i for i,s in enumerate(z['sample_id'])}
    for k,r in enumerate(rows):
        i=index[r['sample_id']];y=z['X_filtered'][i,0];top=100+730*k
        title=f"记录{r['record_id']} · 标注样本{r['annotation_sample']} · {r['true_class']}→{r['predicted_class']}"
        txt(d,(1500,top),title,53,anchor='mm',b=True)
        x0,y0,w,h=260,top+100,2470,430;lo=float(y.min());hi=float(y.max());pad=max((hi-lo)*.12,.05);lo-=pad;hi+=pad
        for q in range(3):
            v=lo+(hi-lo)*q/2;yp=y0+h*(1-q/2);d.line((x0,yp,x0+w,yp),fill='#DDE3E7',width=2);txt(d,(x0-20,yp),f'{v:.1f}',42,anchor='rm')
        pts=[(x0+(float(t)+.3)/.7*w,y0+(hi-float(v))/(hi-lo)*h) for t,v in zip(xx,y)]
        d.line(pts,fill=COL[['N','S','V','F'].index(r['true_class'])],width=5)
        zero=x0+.3/.7*w;d.line((zero,y0,zero,y0+h),fill='#777777',width=2)
        d.line((x0,y0,x0,y0+h,x0+w,y0+h),fill='#333333',width=3)
        for t in [-.3,0,.4]:txt(d,(x0+(t+.3)/.7*w,y0+h+44),f'{t:g} s',42,anchor='mt')
        txt(d,(60,y0+160),'mV',46);txt(d,(1500,top+650),'相对专家标注时间；波形为滤波后物理幅值',42,anchor='mm')
    save(im,'fig11_errors.png')

def nv_partitions():
    rows=[]
    for sp in ['val','test']:
        for r in table(f'results/classification/nv44_v1/{sp}_predictions_cnn_1d.csv'): r['partition']=sp;rows.append(r)
    subjects=sorted(set(r['subject_id'] for r in rows if r['partition']=='val'))+sorted(set(r['subject_id'] for r in rows if r['partition']=='test'))
    im,d=canvas(2300)
    for k,(title,ymax) in enumerate([('各患者N→V误分率（以该患者真实N为分母，%）',100),('各患者真实V心拍数（无V时为0拍）',1000)]):
        b=(240,180+k*1110,2500,740);axis(d,b,title,ymax)
        for i,subj in enumerate(subjects):
            rr=[r for r in rows if r['subject_id']==subj]
            ns=[r for r in rr if r['true_aami_label']=='N']; vs=[r for r in rr if r['true_aami_label']=='V']
            value=(sum(r['predicted_aami_label']=='V' for r in ns)/len(ns)*100) if k==0 else len(vs)
            gw=b[2]/12; x=b[0]+gw*(i+.2); y=b[1]+b[3]*(1-value/ymax);c='#4477AA' if i<6 else '#EE7733'
            d.rectangle((x,y,x+gw*.6,b[1]+b[3]),fill=c)
            txt(d,(x+gw*.3,y-12),f'{value:.2f}' if k==0 else str(value),37,anchor='mb')
            txt(d,(x+gw*.3,b[1]+b[3]+25),subj.replace('subject_',''),40,anchor='mt')
        txt(d,(1500,b[1]+b[3]+115),'受试者编号（左6名为验证分区，右6名为测试分区）',44,anchor='mm')
    save(im,'fig16_nv_partitions.png')

if __name__=='__main__':
    diagrams();statistics();error_cases();nv_partitions()
    print('Redrawn 9 existing figures plus one new partition figure from saved data; source files unchanged.')
