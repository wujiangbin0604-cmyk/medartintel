export class PlaybackClock {
 time:number|null=null; private frame=0;private origin=0;private anchor=0;private listeners=new Set<(time:number|null)=>void>();
 subscribe(fn:(time:number|null)=>void){this.listeners.add(fn);fn(this.time);return()=>{this.listeners.delete(fn);};}
 seek(time:number|null){this.time=time;this.anchor=time??0;this.origin=performance.now();this.refresh();}
 refresh(){this.listeners.forEach(fn=>fn(this.time));}
 stop(){cancelAnimationFrame(this.frame);}
 start(start:number,end:number,speed:number,onUI:(time:number)=>void,onEnd:()=>void){this.stop();this.origin=performance.now();this.anchor=this.time??start;let lastUI=0;const visibility=()=>{this.origin=performance.now();this.anchor=this.time??start;};document.addEventListener('visibilitychange',visibility);
 const tick=(now:number)=>{if(document.hidden){this.origin=now;this.anchor=this.time??start;}const next=Math.min(end,this.anchor+(now-this.origin)/1000*speed);this.time=next;this.refresh();if(now-lastUI>=100||next===end){onUI(next);lastUI=now;}if(next>=end){onEnd();return;}this.frame=requestAnimationFrame(tick);};this.frame=requestAnimationFrame(tick);return()=>{this.stop();document.removeEventListener('visibilitychange',visibility);};}
}
