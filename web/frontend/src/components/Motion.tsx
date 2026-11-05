import React, { useEffect, useRef } from 'react';
import { Card, type CardProps } from 'antd';
import { animate, motion } from 'motion/react';
import { useMotionSettings } from '@/utils/motion';
export function MotionCard({children,...props}:CardProps){const {reduced}=useMotionSettings();return <motion.div className="motion-card-wrap" layout={!reduced} initial={{opacity:0,y:reduced?0:8}} animate={{opacity:1,y:0}} whileHover={reduced?{}:{y:-3}}><Card {...props}>{children}</Card></motion.div>;}
export function AnimatedMetric({value,precision=0,suffix=''}:{value:number;precision?:number;suffix?:string}){
  const node=useRef<HTMLSpanElement>(null); const previous=useRef(0);const {reduced}=useMotionSettings();
  useEffect(()=>{const write=(n:number)=>{if(node.current)node.current.textContent=n.toLocaleString('zh-CN',{minimumFractionDigits:precision,maximumFractionDigits:precision})+suffix;};if(reduced){write(value);previous.current=value;return;}
    const controls=animate(previous.current,value,{duration:0.6,onUpdate:write});previous.current=value;return ()=>controls.stop();},[value,precision,suffix,reduced]);
  return <span ref={node} aria-label={`${value}${suffix}`} className="animated-metric">{value.toLocaleString('zh-CN',{maximumFractionDigits:precision})}{suffix}</span>;
}
export function ProbabilityBar({label,value,selected,onSelect,color}:{label:string;value:number;selected?:boolean;onSelect?:()=>void;color:string}){
  const {reduced}=useMotionSettings();return <button className={`animated-probability ${selected?'probability-selected':''}`} onClick={onSelect} aria-label={`${label} 类概率 ${(value*100).toFixed(2)}%`} aria-pressed={selected} disabled={!onSelect}>
    <span>{label}</span><span className="probability-track"><motion.i initial={reduced?false:{width:0}} animate={{width:`${value*100}%`}} transition={{duration:reduced?0:0.45}} style={{background:color}} /></span><b>{(value*100).toFixed(1)}%</b></button>;
}
export function Reveal({children,id}:{children:React.ReactNode;id:string|number}){const {reduced}=useMotionSettings();return <motion.div key={id} initial={{opacity:reduced?1:0,y:reduced?0:6}} animate={{opacity:1,y:0}} className="prediction-reveal">{children}</motion.div>;}
