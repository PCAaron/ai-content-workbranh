import React,{useEffect,useRef,useState} from "react";
import {createRoot} from "react-dom/client";
import {BookOpenText,Newspaper,Inbox,PenLine,Workflow,ScanText,LogOut,ArrowRight,LibraryBig,Layers3,ShieldCheck} from "lucide-react";
import {api} from "./api";
import {AppCtx,useApp,useLoad,Load,Header,Empty,Btn,Field,go,dataOf,Pill} from "./ui";
import {Library} from "./library";
import {Editor,Manuscripts} from "./editor";
import {Operations,Learning} from "./operations";
import "./style.css";

const nav=[["home","编辑总览",Newspaper],["library","素材与选题",Inbox],["drafts","稿件工作区",PenLine],["learning","文风实验室",ScanText],["runs","运行记录",Workflow]];
function Brand(){return <div className="brand"><BookOpenText size={28}/><b>笺台</b><span>FOLIO</span></div>}
function Login(){
 const {run,setUser}=useApp();
 return <div className="login"><section><Brand/><div className="login-type">编辑部<br/>工作台<span>。</span></div><p>素材、观点与每一版稿件，归于一处。</p></section><form onSubmit={e=>{const d=dataOf(e);run(async()=>setUser(await api("login",d)))}}><h1>登录编辑部</h1><Field label="账号"><input name="username" autoComplete="username" autoFocus required/></Field><Field label="密码"><input name="password" type="password" autoComplete="current-password" required/></Field><Btn>登录 <ArrowRight size={16}/></Btn></form></div>;
}
function Overview(){
 const {stamp}=useApp(); const rec=useLoad("overview",stamp);
 return <><Header title="编辑总览" desc="查看编辑部正在推进的选题、稿件与审核。"><button className="btn" onClick={()=>go("library")}>收集素材 <ArrowRight size={16}/></button></Header><Load record={rec}>{d=><>
 <div className="metrics">{[[Inbox,"来源材料",d.sources,"library"],[LibraryBig,"已确认选题",d.topics,"library"],[Layers3,"在编母稿",d.drafts,"drafts"],[ShieldCheck,"待审母稿",d.review,"drafts"]].map(([Icon,name,count,path])=><button key={name} onClick={()=>go(path)}><Icon size={20}/><span>{name}</span><strong>{count}</strong></button>)}</div>
 <section className="panel"><div className="section-head"><h2>最近稿件</h2><a href="#drafts">查看稿件库 →</a></div>{d.recent.length?d.recent.map(x=><a className="row" key={x.id} href={"#draft/"+x.id}><b>{x.topic__title}</b><Pill>{x.version?"v"+x.version:"待起稿"}</Pill></a>):<Empty title="还没有稿件">先保存一条来源材料与一句本人原话，再确认第一条选题。</Empty>}</section></>}</Load></>
}
function App(){
 const [user,setUser]=useState(null),[error,setError]=useState(""),[message,setMessage]=useState(""),[busy,setBusy]=useState(false),[stamp,refresh]=useState(0);
 const lock=useRef(false),[route,setRoute]=useState(location.hash.slice(1)||"home");
 useEffect(()=>{api("session").then(setUser).catch(e=>setError(e.message));
 const hash=()=>{setRoute(location.hash.slice(1)||"home");setError("");setMessage("")};
 const out=()=>api("session").then(setUser);
 window.addEventListener("hashchange",hash);window.addEventListener("signed-out",out);
 return ()=>{window.removeEventListener("hashchange",hash);window.removeEventListener("signed-out",out)}},[]);
 const run=async(fn,msg)=>{if(lock.current)return;lock.current=true;setBusy(true);setError("");setMessage("");
 try{await fn();if(msg)setMessage(msg);refresh(n=>n+1)}catch(e){setError(e.message)}finally{lock.current=false;setBusy(false)}};
 const [page,id]=route.split("/"),active=page==="draft"?"drafts":page;
 const value={user,setUser,run,busy,stamp,refresh:()=>refresh(n=>n+1),reviewer:user?.role==="reviewer"};
 return <AppCtx.Provider value={value}>{error&&<div className="toast bad" role="alert">{error}<button onClick={()=>setError("")}>关闭</button></div>}{message&&<div className="toast" role="status">{message}<button onClick={()=>setMessage("")}>关闭</button></div>}
 {!user?<main>正在连接编辑部…</main>:!user.user?<Login/>:<div className="shell"><aside><Brand/><nav>{nav.map(([key,name,Icon])=><a key={key} href={"#"+key} aria-current={active===key?"page":undefined}><Icon size={18}/>{name}</a>)}</nav><footer><div><b>{user.user}</b><small>{value.reviewer?"审核员":"编辑"}</small></div><button title="退出登录" aria-label="退出登录" onClick={()=>run(async()=>{await api("logout",{});setUser(await api("session"))})}><LogOut size={18}/></button></footer></aside>
 <main><div className="crumb">编辑部 <span>/</span> {nav.find(n=>n[0]===active)?.[1]||"页面"}</div>{page==="library"?<Library/>:page==="drafts"?<Manuscripts/>:page==="draft"&&/^\d+$/.test(id)?<Editor key={id} id={id}/>:page==="runs"?<Operations/>:page==="learning"?<Learning/>:<Overview/>}</main></div>}</AppCtx.Provider>
}
createRoot(document.getElementById("root")).render(<App/>);
