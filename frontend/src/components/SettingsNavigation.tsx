import { ChevronRight, User, ShieldCheck, Bell, Mic, Palette, CircleHelp, LockKeyhole, Wallet, ReceiptText, Calendar, type LucideIcon } from "lucide-react";
type Destination='wallet'|'accounts'|'activity'|'bills';
type Row={name:string;hint:string;Icon:LucideIcon;destination?:Destination};
const groups:{title:string;rows:Row[]}[] = [
  { title: "Your account", rows: [{name:"Personal Details", hint:"About this demo account", Icon:User},{name:"Wallet",hint:"Available, posted and reserved funds",Icon:Wallet,destination:'wallet'},{name:"Accounts & Cards",hint:"Payment methods and connection state",Icon:Wallet,destination:'accounts'}] },
  { title: "Payments & security", rows: [{name:"Security", hint:"Wallet PIN and secure approvals", Icon:LockKeyhole}, {name:"AutoPay & Permissions", hint:"Businesses, limits and expiry", Icon:ShieldCheck},{name:"Statements & Receipts",hint:"Actual payment records and documents",Icon:ReceiptText,destination:'activity'},{name:"Bills & Subscriptions",hint:"Expected expenses and reminders",Icon:Calendar,destination:'bills'}] },
  { title: "Preferences", rows: [{name:"Notifications", hint:"Alerts, quiet hours and privacy", Icon:Bell}, {name:"AI & Voice", hint:"Listening and spoken replies", Icon:Mic}, {name:"Appearance", hint:"Light, dark or device theme", Icon:Palette}] },
  { title: "Privacy & support", rows: [{name:"Privacy & Data", hint:"Microphone, conversations and records", Icon:ShieldCheck}, {name:"Help & About", hint:"How this prototype works", Icon:CircleHelp}] },
];
export function SettingsNavigation({section,onSelect,onNavigate}:{section:string;onSelect:(section:string)=>void;onNavigate:(destination:Destination)=>void}) {
  return <nav className={`settings-navigation ${section !== "Overview" ? "has-detail" : ""}`} aria-label="Settings sections">
    {groups.map(group=><section key={group.title}><h2>{group.title}</h2><div className="settings-row-group">{group.rows.map(({name,hint,Icon,destination})=><button key={name} aria-label={name} aria-current={section===name?"page":undefined} onClick={()=>destination?onNavigate(destination):onSelect(name)}><Icon size={20}/><span><strong>{name}</strong><small>{hint}</small></span><ChevronRight size={17}/></button>)}</div></section>)}
  </nav>;
}
