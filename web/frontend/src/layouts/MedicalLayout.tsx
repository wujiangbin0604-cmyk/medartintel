import React, { useEffect, useRef, useState } from 'react';
import { Link, useOutlet, useLocation } from '@umijs/max';
import { Badge, Button, Select, Tooltip } from 'antd';
import { HeartOutlined, DashboardOutlined, FundProjectionScreenOutlined, LineChartOutlined, ExperimentOutlined, BarChartOutlined, PictureOutlined, MenuFoldOutlined, MenuUnfoldOutlined,DatabaseOutlined,DeploymentUnitOutlined,UserOutlined } from '@ant-design/icons';
import {ECGMark,SidebarArt} from '@/components/MedicalVisuals';
import { AnimatePresence, motion } from 'motion/react';
import { useMotionSettings } from '@/utils/motion';
import WelcomeOnboarding from '@/components/onboarding/WelcomeOnboarding';
import '../global.less';
import '../styles/medical.less';
import '../styles/fidelity.less';
const links=[['/dashboard','项目总览',DashboardOutlined,'Dashboard'],['/ai-detection','ECG 波形分析',LineChartOutlined,'ECG workspace'],['/ai-inference','AI 智能检测',HeartOutlined,'AI detection'],['/experiments','模型实验中心',ExperimentOutlined,'Model experiments'],['/generalization','错误与泛化分析',BarChartOutlined,'Generalization'],['/gallery','科研可视化图库',PictureOutlined,'Research gallery'],['/presentation-demo','课程答辩演示',FundProjectionScreenOutlined,'Presentation'],['/interactive-lab','心电互动实验室',ExperimentOutlined,'ECG Interactive Lab']] as const;
export default function MedicalLayout(){
 const location=useLocation();const outlet=useOutlet();const {mode,setMode,reduced,duration}=useMotionSettings();
 const [collapsed,setCollapsed]=useState(false);const [health,setHealth]=useState({status:'processing' as 'success'|'error'|'processing',models:0});
 const [narrow,setNarrow]=useState(window.innerWidth<1000);const [expanded,setExpanded]=useState(false);const compact=collapsed||(narrow&&!expanded);
 useEffect(()=>{const media=matchMedia('(max-width:999px)');const update=()=>{setNarrow(media.matches);setExpanded(false);};media.addEventListener('change',update);return()=>media.removeEventListener('change',update);},[]);
 const positions=useRef<Record<string,number>>({});const currentPath=useRef(location.pathname);
 useEffect(()=>{const controller=new AbortController();fetch('/api/health',{signal:controller.signal}).then(r=>r.json()).then(d=>setHealth({status:d.models_loaded===d.models_total?'success':'error',models:d.models_loaded})).catch(()=>{if(!controller.signal.aborted)setHealth({status:'error',models:0});});return()=>controller.abort();},[]);
 useEffect(()=>{const save=()=>{positions.current[currentPath.current]=window.scrollY;};window.addEventListener('scroll',save,{passive:true});return()=>window.removeEventListener('scroll',save);},[]);
 useEffect(()=>{currentPath.current=location.pathname;const timer=window.setTimeout(()=>window.scrollTo(0,positions.current[location.pathname]||0),reduced?0:180);return()=>clearTimeout(timer);},[location.pathname,reduced]);
 const navActive=(url:string)=>location.pathname===url||(url==='/interactive-lab'&&location.pathname.startsWith('/interactive-lab/'));
 return <div className={`platform ${compact?'sidebar-collapsed':''} ${narrow&&expanded?'sidebar-expanded':''}`}>
  <header className="platform-header"><Link to="/dashboard" className="platform-brand"><span className="brand-symbol"><ECGMark/></span><strong>ECG-AI <em>心电智能分析平台</em></strong></Link><span className="header-description">基于深度学习的心电图自动分析与分类</span><div className="header-right"><Badge status={health.status} text={health.status==='success'?'系统运行正常':health.status==='error'?'服务不可用':'连接本地服务'} /><span className="header-models"><DeploymentUnitOutlined/> {health.models} 个模型就绪</span><span className="header-dataset"><DatabaseOutlined/> 数据集：MIT-BIH</span><Select aria-label="动画强度" value={mode} onChange={setMode} options={[{value:'full',label:'完整动效'},{value:'standard',label:'标准动效'},{value:'reduced',label:'减少动效'}]} /><Tooltip title="本地课程研究项目"><span className="header-avatar"><UserOutlined/></span></Tooltip></div></header>
  <aside className="platform-sidebar"><Button className="collapse-toggle" type="text" aria-label={compact?'展开侧边栏':'收起侧边栏'} icon={compact?<MenuUnfoldOutlined/>:<MenuFoldOutlined/>} onClick={()=>narrow?setExpanded(v=>!v):setCollapsed(v=>!v)}>{!compact&&'项目导航'}</Button><nav className="platform-nav" aria-label="主导航">{links.map(([url,label,Icon])=><Tooltip key={url} title={compact?label:undefined} placement="right"><Link to={url} onClick={()=>setExpanded(false)} aria-label={label} className={navActive(url)?'active':''} aria-current={location.pathname===url?'page':undefined}><Icon/>{!compact&&<span>{label}</span>}{navActive(url)&&<motion.i layoutId="navigation-active" className="nav-indicator" transition={{duration:reduced?0:0.25}}/>}</Link></Tooltip>)}{!compact&&<Link to="/interactive-lab/heartbeat-hunter" className={`hunter-nav-child ${location.pathname.endsWith('heartbeat-hunter')?'active':''}`}><span>•</span> Heartbeat Hunter · 心跳猎人</Link>}</nav><div className="sidebar-signal"><SidebarArt/></div></aside>
  <div className="platform-main"><AnimatePresence mode="wait" initial={false}><motion.div key={location.pathname} initial={{opacity:0,y:reduced?0:8}} animate={{opacity:1,y:0}} exit={{opacity:0,y:reduced?0:-4}} transition={{duration:duration*0.7}}>{outlet}</motion.div></AnimatePresence><footer className="platform-footer">MIT-BIH 历史数据 · 专家标签作为参考 · 模型概率未经临床校准</footer></div><WelcomeOnboarding/>
 </div>;
}

