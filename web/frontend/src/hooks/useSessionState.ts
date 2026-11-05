import { useEffect, useState } from 'react';
export default function useSessionState<T>(key:string, initial:T){
  const [value,setValue]=useState<T>(()=>{try{const saved=sessionStorage.getItem(key);return saved===null?initial:JSON.parse(saved);}catch{return initial;}});
  useEffect(()=>{try{sessionStorage.setItem(key,JSON.stringify(value));}catch{/* Storage may be disabled; retain in-memory state. */}},[key,value]);
  return [value,setValue] as const;
}
