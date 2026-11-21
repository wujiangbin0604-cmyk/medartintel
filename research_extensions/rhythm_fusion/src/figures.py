"""PNG + SVG scientific figures generated exclusively from completed artifacts."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from .data import BASE, load
from research_extensions.protect import sha256
from .run import write

COLORS=["#1677ff","#13a2a2","#4059a9","#8295ab"]


def generate(run_id="cv_cpu_v1", output_directory=None):
    folder=BASE/"results"/run_id
    summary=json.loads((folder/"summary.json").read_text(encoding="utf-8"))
    bpath=BASE.parent/f"uncertainty/results/{run_id}/summary.json"
    uncertainty=json.loads(bpath.read_text(encoding="utf-8")) if bpath.is_file() else None
    output=Path(output_directory) if output_directory is not None else BASE/"figures"/run_id
    output.mkdir(parents=True,exist_ok=True)
    seed=summary["config"]["seeds"][0]
    models=[m for m in summary["models"] if m["seed"]==seed]
    classes=summary["classes"]; data=load()
    caption=f"Original train+val only | {summary['subject_count']} patient groups | {summary['config']['outer_folds']}-fold outer OOF | seed {seed} | max {summary['config']['epochs']} epochs"
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"svg.fonttype":"none"})
    catalog=[]
    def save(fig,name,meaning,unit="heartbeat",all_seeds=False):
        scope=caption.replace(f"seed {seed}",f"seeds {','.join(map(str,summary['config']['seeds']))}") if all_seeds else caption
        fig.text(.5,.012,scope+"\n"+meaning,ha="center",va="bottom",fontsize=7,color="#536b82",wrap=True)
        fig.tight_layout(rect=[0,.08,1,.97])
        for ext in ["png","svg"]:
            fig.savefig(output/f"{name}.{ext}",dpi=300,bbox_inches="tight")
        plt.close(fig)
        catalog.append({"name":name,"png":f"{name}.png","vector":f"{name}.svg","scope":scope,"evaluation_unit":unit,"meaning":meaning,
                        "source":str((folder/"summary.json").relative_to(BASE)),"source_sha256":sha256(folder/"summary.json")})
    fig,ax=plt.subplots(figsize=(11,4));ax.set_axis_off()
    boxes=[(.02,.54,.38,.28,"Waveform [B,1,253]\nConv/Pool x2 + Conv/AvgPool -> 64"),(.02,.14,.38,.28,"7 past-only RR features + 7 masks\nLinear 14->32->16 + ReLU"),(.61,.33,.35,.3,"Concatenate [B,80]\nLinear 80->4 -> N/S/V/F")]
    for x,y,w,h,text in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.02",facecolor="#f0f7fd",edgecolor="#1677ff",transform=ax.transAxes))
        ax.text(x+w/2,y+h/2,text,ha="center",va="center",transform=ax.transAxes)
    for y in [.68,.28]:ax.annotate("",xy=(.60,.48),xytext=(.42,y),arrowprops={"arrowstyle":"->","color":"#13a2a2"},xycoords="axes fraction")
    ax.set_title("RhythmMorphologyCNN: implemented tensor structure")
    save(fig,"01_architecture","Architecture schematic, not neuron activation; CNN encoder identical to original HeartbeatCNN.","model structure")
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for j,(feature,title) in enumerate([(0,"Current RR (s)"),(3,"Current RR / historical median")]):
        for i,c in enumerate(classes):
            values=data["rhythm_features"][data["label"]==i,feature];values=values[np.isfinite(values)]
            axes[j].hist(values,bins=70,histtype="step",density=True,label=f"{c} n={len(values)}",color=COLORS[i],linewidth=1.3)
        axes[j].set(xlabel=title,ylabel="Density (log scale)",yscale="log");axes[j].legend(fontsize=8)
    save(fig,"02_rr_distribution","Descriptive development feature distributions; original expert-event positions, no target-only RR sequence.")
    fig,ax=plt.subplots(figsize=(8,4))
    ax.bar([m["model"] for m in models],[m["pooled"]["macro_f1"] for m in models],color=COLORS)
    for i,m in enumerate(models):ax.text(i,m["pooled"]["macro_f1"]+.015,f"{m['pooled']['macro_f1']:.4f}",ha="center")
    ax.set(ylim=(0,1),ylabel="Pooled OOF Macro-F1",title="All four prespecified ablations")
    save(fig,"03_macro_f1","Pooled OOF across all folds, no best fold selection; parameter counts reported separately.")
    fig,ax=plt.subplots(figsize=(10,4))
    xs=np.arange(len(classes));width=.19
    for i,m in enumerate(models):ax.bar(xs+(i-1.5)*width,[m["pooled"]["per_class"][c]["f1"] for c in classes],width,label=m["model"],color=COLORS[i])
    supports=models[0]["pooled"]["per_class"]
    ax.set_xticks(xs,[f"{c}\nn={supports[c]['support']}, patients={supports[c]['subject_count']}" for c in classes])
    ax.set(ylim=(0,1),ylabel="F1",title="Class-specific OOF F1 and independent patient support");ax.legend(ncol=4)
    save(fig,"04_class_f1","Fixed N/S/V/F label set; F support must be read with patient concentration.")
    fig,axes=plt.subplots(1,4,figsize=(13,4))
    for ax,m in zip(axes,models):
        cm=np.array(m["pooled"]["confusion_matrix"]);norm=cm/np.maximum(cm.sum(1,keepdims=True),1)
        ax.imshow(norm,vmin=0,vmax=1,cmap="Blues")
        for i in range(4):
            for j in range(4):ax.text(j,i,str(cm[i,j]),ha="center",va="center",fontsize=7,color="white" if norm[i,j]>.55 else "#213b55")
        ax.set(xticks=range(4),xticklabels=classes,yticks=range(4),yticklabels=classes,xlabel="Predicted",ylabel="True",title=m["model"])
    save(fig,"05_confusion_matrices","Cell text: actual counts; color: row-normalized recall, common 0-1 scale.")
    subjects=sorted(set(data["subject_group"]));fig,ax=plt.subplots(figsize=(14,4))
    for model,color in [("A0",COLORS[0]),("A2",COLORS[2])]:
        rows={r["subject"]:r for r in summary["patients"] if r["model"]==model and r["seed"]==seed}
        ax.plot(range(len(subjects)),[rows[g]["macro_f1"] for g in subjects],"o-",label=model,color=color,markersize=3)
    ax.set_xticks(range(len(subjects)),[g.replace("subject_","") for g in subjects],rotation=75);ax.set(ylabel="Patient Macro-F1",ylim=(0,1),title="Per-patient comparison (absent classes score zero)");ax.legend()
    save(fig,"06_patient_performance","One point per patient group, fixed four-class Macro-F1; not patient-independent repeated observations.","patient group")
    fig,ax=plt.subplots(figsize=(9,4))
    for i,model in enumerate(summary["config"]["models"]):
        for sd in summary["config"]["seeds"]:
            rows=sorted([r for r in summary["folds"] if r["model"]==model and r["seed"]==sd],key=lambda r:r["fold"])
            ax.plot([r["fold"]+1 for r in rows],[r["macro_f1"] for r in rows],"o-",label=f"{model} seed {sd}",color=COLORS[i])
    ax.set(xlabel="Outer fold",ylabel="Macro-F1",ylim=(0,1),xticks=range(1,6),title="Fold variability; no unexecuted seeds represented");ax.legend(fontsize=8,ncol=2)
    save(fig,"07_fold_seed_variability","Fold variation is descriptive; shared training patients make folds dependent.","patient-group fold",all_seeds=True)
    transitions=[r for r in summary["error_transitions"] if r["seed"]==seed]
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    keys=["both_correct","corrected_by_fusion","new_errors_with_fusion","both_wrong"]
    axes[0].bar(range(4),[sum(r[k] for r in transitions) for k in keys],color=["#8295ab","#13a2a2","#cd7466","#4059a9"])
    axes[0].set_xticks(range(4),["Both correct","Corrected","New error","Both wrong"],rotation=15);axes[0].set_ylabel("Heartbeats")
    deltas=[r["delta_macro_f1"] for r in transitions]
    axes[1].bar(range(len(deltas)),deltas,color=["#13a2a2" if x>=0 else "#cd7466" for x in deltas]);axes[1].axhline(0,color="#536b82",lw=.7)
    axes[1].set(xlabel="Patient (sorted)",ylabel="A2 - A0 patient Macro-F1")
    save(fig,"08_error_transitions","Paired same-sample OOF comparison; corrected errors and new errors both retained.")
    if uncertainty:
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for ax,method in zip(axes,["max_score","entropy"]):
            for i,name in enumerate(summary["config"]["models"]):
                rows=[r for r in uncertainty["risk_coverage"] if r["seed"]==seed and r["model"]==name and r["method"]==method]
                xx=[];yy=[]
                for c in [.1,.2,.3,.4,.5,.6,.7,.8,.9,1.]:
                    point=[r for r in rows if r["nominal_coverage"]==c];xx.append(np.mean([r["coverage"] for r in point]));yy.append(np.mean([r["risk"] for r in point]))
                ax.plot(xx,yy,label=name,color=COLORS[i])
            ax.set(xlabel="Coverage",ylabel="Accepted error rate",title=method);ax.legend()
        save(fig,"09_risk_coverage","Equal-fold mean descriptive score sweeps with tied scores retained; deployment thresholds use separate calibration patients.")
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for ax,method in zip(axes,["max_score","entropy"]):
            for i,name in enumerate(summary["config"]["models"]):
                result=next(r for r in uncertainty["results"] if r["model"]==name and r["seed"]==seed and r["method"]==method)
                ax.bar(xs+(i-1.5)*width,[1-result["per_class"][c]["acceptance_rate"] for c in classes],width,label=name,color=COLORS[i])
            ax.set(xticks=xs,xticklabels=classes,ylabel="Rejection fraction",ylim=(0,1),title=method);ax.legend(ncol=4,fontsize=8)
        save(fig,"10_class_rejection","Fixed calibration-patient 90th-percentile thresholds; per-class denominator is all true-class OOF beats.")
        fig,ax=plt.subplots(figsize=(14,4))
        for color,method in [(COLORS[0],"max_score"),(COLORS[1],"entropy")]:
            per_patient=[]
            for g in subjects:
                values=[next(p["rejection_rate"] for p in r["patients"] if p["subject"]==g)
                        for r in uncertainty["results"] if r["model"]=="A2" and r["method"]==method]
                per_patient.append(float(np.mean(values)))
            ax.plot(range(len(subjects)),per_patient,"o-",label=method,color=color,markersize=3)
        ax.set_xticks(range(len(subjects)),[g.replace("subject_","") for g in subjects],rotation=75)
        ax.set(ylabel="Rejection fraction",ylim=(0,1),title="A2 per-patient rejection; mean across all completed seeds");ax.legend()
        save(fig,"11_patient_rejection","All completed seeds averaged within each patient; fixed independently calibrated thresholds; not a new patient cohort.","patient group",all_seeds=True)
    if len(summary["config"]["seeds"])>1:
        fig,axes=plt.subplots(1,2,figsize=(11,4))
        for i,name in enumerate(summary["config"]["models"]):
            values=[m["pooled"]["macro_f1"] for m in summary["models"] if m["model"]==name]
            axes[0].bar(i,np.mean(values),yerr=np.std(values,ddof=1),color=COLORS[i],capsize=5)
            axes[0].scatter(np.full(len(values),i),values,color="#213b55",s=15)
            seed_values=[next(r["pooled"]["macro_f1"] for r in summary["models"] if r["model"]==name and r["seed"]==sd) for sd in summary["config"]["seeds"]]
            axes[1].plot([str(sd) for sd in summary["config"]["seeds"]],seed_values,"o-",color=COLORS[i],label=name)
        axes[0].set(xticks=range(4),xticklabels=summary["config"]["models"],ylim=(0,1),ylabel="Pooled OOF Macro-F1",title="Mean + sample SD across seeds")
        axes[1].set(ylim=(0,1),xlabel="Training seed",ylabel="Pooled OOF Macro-F1",title="Every completed seed");axes[1].legend()
        save(fig,"12_seed_comparison","All completed seeds; error bars show sample SD of training randomness, not independent-patient SE or CI.","training seed (same patient cohort)",all_seeds=True)
        fig,axes=plt.subplots(1,4,figsize=(13,4))
        for ax,c in zip(axes,classes):
            for i,name in enumerate(summary["config"]["models"]):
                values=[m["pooled"]["per_class"][c]["f1"] for m in summary["models"] if m["model"]==name]
                ax.bar(i,np.mean(values),yerr=np.std(values,ddof=1),capsize=3,color=COLORS[i],alpha=.75)
                ax.scatter(i+np.linspace(-.08,.08,len(values)),values,color="#213b55",s=12,zorder=4)
            ax.set(xticks=range(4),xticklabels=summary["config"]["models"],ylim=(0,1),ylabel="OOF F1",title=f"{c}: n={supports[c]['support']}, patients={supports[c]['subject_count']}")
        save(fig,"13_class_seed_variability","Dots are every seed; bars are mean + sample SD, not a patient CI. Rare-class seed variability must remain visible.","training seed (same patient cohort)",all_seeds=True)
    write(output/"catalog.json",catalog)
    print(f"Generated {len(catalog)} PNG+SVG figure pairs in {output}")


if __name__=="__main__":generate()
