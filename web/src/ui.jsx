import React,{useContext,useEffect,useState,createContext} from "react";
import {ArrowUpRight,FileText,LoaderCircle} from "lucide-react";
import {api} from "./api";
export const AppCtx=createContext(null);
export const useApp=()=>useContext(AppCtx);
export const go=path=>{location.hash=path};
export function useLoad(path,stamp=0){
  const [record,set]=useState({path:null,data:null,error:""});
  useEffect(()=>{let live=true;
    api(path).then(data=>live&&set({path,data,error:""})).catch(e=>live&&set({path,error:e.message,data:null}));
    return ()=>{live=false};
  },[path,stamp]);
  return record.path===path?record:{data:null,error:""};
}
export function Load({record,children}){if(record.error)return <p role="alert" className="error">{record.error}</p>;if(!record.data)return <p className="muted"><LoaderCircle size={16}/> 正在读取…</p>;return children(record.data)}
export function Header({title,desc,children}){return <header className="page-head"><div><h1>{title}</h1>{desc&&<p>{desc}</p>}</div><div>{children}</div></header>}
export function Empty({title,children}){return <div className="empty"><FileText size={24}/><h3>{title}</h3>{children&&<p>{children}</p>}</div>}
export function Field({label,children}){return <label className="field"><span>{label}</span>{children}</label>}
export function Pill({children}){return <span className="pill">{children}</span>}
export function Link({href,children}){return <a className="external" href={href} target="_blank" rel="noreferrer">{children} <ArrowUpRight size={14}/></a>}
export function dataOf(event){event.preventDefault();return Object.fromEntries(new FormData(event.currentTarget))}
export function Btn({children,secondary=false,...props}){const {busy}=useApp();return <button {...props} disabled={busy||props.disabled} className={secondary?"btn secondary":"btn"}>{children}</button>}
