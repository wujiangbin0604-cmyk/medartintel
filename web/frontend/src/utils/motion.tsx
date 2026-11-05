import React, { createContext, useContext, useEffect, useState } from 'react';
import { MotionConfig } from 'motion/react';
import { browserStorage } from './browserStorage';
export type MotionMode = 'full' | 'standard' | 'reduced';
export const easing = [0.22, 1, 0.36, 1] as const;
export const spring = { type: 'spring' as const, stiffness: 360, damping: 32 };
const Context = createContext({mode:'standard' as MotionMode,setMode:(_:MotionMode)=>{},reduced:false,duration:0.3});
export function AnimationProvider({children}:{children:React.ReactNode}) {
  const [mode,setMode]=useState<MotionMode>(()=>{try{return (localStorage.getItem('ecg.motion') as MotionMode)||'standard';}catch{return 'standard';}});
  const [system,setSystem]=useState(()=>matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(()=>{const query=matchMedia('(prefers-reduced-motion: reduce)');const update=()=>setSystem(query.matches);query.addEventListener('change',update);return()=>query.removeEventListener('change',update);},[]);
  const reduced=system||mode==='reduced';
  useEffect(()=>{document.documentElement.dataset.motion=reduced?'reduced':mode;browserStorage.setItem('ecg.motion',mode);},[mode,reduced]);
  return <Context.Provider value={{mode,setMode,reduced,duration:reduced?0:mode==='full'?0.42:0.28}}><MotionConfig reducedMotion={reduced?'always':'user'} transition={{duration:reduced?0:0.28,ease:easing}}>{children}</MotionConfig></Context.Provider>;
}
export const useMotionSettings=()=>useContext(Context);
