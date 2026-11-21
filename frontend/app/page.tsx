'use client';
import {useEffect,useRef,useState} from 'react';
import {Film,Upload,Link2,Play,Download,Scissors,Plus,ArrowUp,ArrowDown,Trash2,RefreshCcw,CheckCircle2,AlertTriangle,LogOut,X,Settings2} from 'lucide-react';

type Media={id:string;filename:string;duration:number;width:number;height:number;size:number;has_audio?:boolean};
type Span={start:number;end:number};
type Clip={id:string;title:string;segments:Span[];duration:number;origin:string;reasoning:string;rendered:boolean;options:{ratio:string;mode:string;crf:number}};
type Job={id:string;status:string;stage:string;error?:string;kind:string;settings?:{candidate_count?:number}};
async function api<T>(path:string,opts:RequestInit={}) : Promise<T>{
  const res=await fetch(`/api${path}`,{credentials:'same-origin',cache:'no-store',...opts,headers:{...(opts.body?{'Content-Type':'application/json'}:{}),...opts.headers}});
  if(!res.ok){let detail='Request failed';try{const data=await res.json();detail=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail)}catch{}throw new Error(detail)}
  return res.json();
}
const json=(x:unknown)=>JSON.stringify(x);
const fmt=(sec:number)=>{const n=Math.max(0,Math.floor(sec));return `${Math.floor(n/60)}:${String(n%60).padStart(2,'0')}`};
const sizes=(size:number)=>`${(size/1024/1024).toFixed(1)} MB`;

export default function Home(){
  const [logged,setLogged]=useState(false);const [checking,setChecking]=useState(true);const [password,setPassword]=useState('');const [error,setError]=useState('');
  const [active,setActive]=useState<Media|null>(null);const [recent,setRecent]=useState<Media[]>([]);const [clips,setClips]=useState<Clip[]>([]);const [job,setJob]=useState<Job|null>(null);
  const [file,setFile]=useState<File|null>(null);const [rights,setRights]=useState(false);const [consent,setConsent]=useState(false);const [busy,setBusy]=useState(false);const [uploadPct,setUploadPct]=useState<number|null>(null);
  const [yt,setYt]=useState('');const [ytResult,setYtResult]=useState('');const [category,setCategory]=useState('auto');const [maxClips,setMaxClips]=useState(3);
  const [title,setTitle]=useState('Selected highlight');const [segments,setSegments]=useState<Span[]>([{start:0,end:20}]);
  const [ratio,setRatio]=useState('original');const [mode,setMode]=useState('fit');const [quality,setQuality]=useState(20);
  const [editing,setEditing]=useState<string|null>(null);const stop=useRef(false);const cancel=useRef<AbortController|null>(null);
  const [panel,setPanel]=useState<'upload'|'youtube'>('upload');

  const refresh=async()=>{try{const m=await api<Media[]>('/media');setRecent(m)}catch{}};
  const refreshClips=async(id:string)=>{const c=await api<Clip[]>(`/media/${id}/clips`);setClips(c)};
  useEffect(()=>{api('/me').then(()=>{setLogged(true);refresh()}).catch(()=>{}).finally(()=>setChecking(false))},[]);
  useEffect(()=>{if(!job || ['done','failed','blocked','cancelled'].includes(job.status))return;const interval=setInterval(async()=>{try{const j=await api<Job>(`/jobs/${job.id}`);setJob(j);if(['done','failed','blocked','cancelled'].includes(j.status)&&active)refreshClips(active.id)}catch{}},1400);return()=>clearInterval(interval)},[job?.id,job?.status,active?.id]);
  const login=async(e:React.FormEvent)=>{e.preventDefault();setError('');try{await api('/auth/login',{method:'POST',body:json({password})});setPassword('');setLogged(true);refresh()}catch(e){setError((e as Error).message)}};
  const openMedia=async(m:Media)=>{setActive(m);setJob(null);setError('');setEditing(null);setSegments([{start:0,end:Math.min(20,m.duration)}]);setClips(await api<Clip[]>(`/media/${m.id}/clips`))};
  const upload=async()=>{
    if(!file||!rights)return setError('Choose a file and confirm processing rights');setBusy(true);setError('');stop.current=false;cancel.current=new AbortController();
    try{
      const key=`clipra-next:${file.name}:${file.size}:${file.lastModified}`;
      let record: {id:string}|null=null;
      try{record=JSON.parse(localStorage.getItem(key)||'null')}catch{}
      let id=record?.id,offset=0;
      if(id){const head=await fetch(`/api/uploads/${id}`,{method:'HEAD',credentials:'same-origin'});if(head.ok)offset=Number(head.headers.get('Upload-Offset')||0);else id=undefined}
      if(!id){const r=await api<{id:string}>('/uploads',{method:'POST',body:json({filename:file.name,size:file.size,rights_confirmed:rights})});id=r.id;localStorage.setItem(key,json({id}));}
      const chunkSize=4*1024*1024;
      while(offset<file.size){if(stop.current)throw new Error('Upload paused. Choose the same file to resume.');
        let tries=0;
        while(true){try{const part=file.slice(offset,offset+chunkSize);const res=await fetch(`/api/uploads/${id}`,{method:'PATCH',credentials:'same-origin',body:part,signal:cancel.current.signal,
          headers:{'Upload-Offset':String(offset),'Tus-Resumable':'1.0.0','Content-Type':'application/offset+octet-stream'}});
          if(!res.ok)throw Error(`Upload request failed (${res.status})`);offset=Number(res.headers.get('Upload-Offset'));break;
        }catch(e){if(stop.current)throw e;tries++;if(tries>3)throw e;const head=await fetch(`/api/uploads/${id}`,{method:'HEAD'});if(head.ok)offset=Number(head.headers.get('Upload-Offset')||offset);await new Promise(resolve=>setTimeout(resolve,500*tries));}}
        setUploadPct(Math.round(offset/file.size*100));
      }
      const info=await api<Media>(`/uploads/${id}/complete`,{method:'POST'});localStorage.removeItem(key);setFile(null);setUploadPct(null);await refresh();await openMedia(info);
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  };
  const analyze=async()=>{if(!active)return;setError('');try{const j=await api<Job>(`/media/${active.id}/analyze`,{method:'POST',body:json({category,max_clips:maxClips,consent})});setJob(j)}catch(e){setError((e as Error).message)}};
  const editClip=(c:Clip)=>{setEditing(c.id);setSegments(c.segments.map(s=>({...s})));setTitle(c.title);setRatio(c.options?.ratio||'original');setMode(c.options?.mode||'fit');setQuality(c.options?.crf||20)};
  const saveClip=async()=>{if(!active)return;setError('');try{
    const body={title,segments:segments.map(s=>({start:Number(s.start),end:Number(s.end)})),ratio,mode,crf:quality};
    const c=await api<Clip>(editing?`/clips/${editing}`:`/media/${active.id}/clips`,{method:editing?'PUT':'POST',body:json(body)});
    await refreshClips(active.id);setEditing(null);
    return c;
  }catch(e){setError((e as Error).message)}};
  const exportClip=async(id:string)=>{setError('');try{const j=await api<Job>(`/clips/${id}/render`,{method:'POST'});setJob(j)}catch(e){setError((e as Error).message)}};
  const addSpan=()=>setSegments(s=>[...s,{start:0,end:Math.min(10,active?.duration||10)}]);
  const swap=(i:number,to:number)=>setSegments(s=>{const x=[...s];[x[i],x[to]]=[x[to],x[i]];return x});
  const inspectYt=async()=>{setYtResult('');setError('');try{const result=await api<{message:string,video_id:string}>('/youtube/inspect',{method:'POST',body:json({url:yt})});setYtResult(`${result.message} Video ID: ${result.video_id}`)}catch(e){setError((e as Error).message)}};
  if(checking)return <main className="center"><span>Loading CLIPRA AI NEXT…</span></main>;
  if(!logged)return <main className="center"><form className="login" onSubmit={login}><div className="logo"><Film size={25}/> CLIPRA <span>AI NEXT</span></div><h1>Welcome back</h1><p>Log in to your private video workspace.</p><input type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Workspace password" required/><button className="primary" type="submit">Open workspace</button>{error&&<p className="err">{error}</p>}</form></main>;
  return <div className="shell"><header><div className="logo"><Film size={23}/> CLIPRA <span>AI NEXT</span></div><div className="headRight"><span className="private">PRIVATE WORKSPACE</span><button className="ghost" title="Logout" onClick={async()=>{await api('/auth/logout',{method:'POST'});setLogged(false);setActive(null)}}><LogOut size={18}/></button></div></header>
    <main><div className="hero"><div className="eyebrow">VIDEO WORKSPACE / 01</div><h1>Make every moment count.</h1><p>Import footage. Discover real moments. Control every edit. Export the actual video.</p></div>
    {error&&<div className="error"><AlertTriangle size={18}/>{error}<button onClick={()=>setError('')}><X size={17}/></button></div>}
    {!active ? <><section className="import"><div className="tabs"><button className={panel==='upload'?'selected':''} onClick={()=>setPanel('upload')}><Upload size={17}/> Gallery / Files</button><button className={panel==='youtube'?'selected':''} onClick={()=>setPanel('youtube')}><Link2 size={17}/> YouTube Link</button></div>
      {panel==='upload'?<div className="importContent"><div className="drop"><Upload size={27}/><h2>Upload your original video</h2><p>MP4, MOV, WebM, and other FFmpeg-supported formats. Up to 10 GB configured.</p><label className="filebutton">Choose video <input type="file" accept="video/*,.mp4,.mov,.webm,.mkv" onChange={e=>setFile(e.target.files?.[0]||null)} /></label>{file&&<div className="chosen"><Film size={17}/>{file.name} <span>{sizes(file.size)}</span></div>}</div>
        <label className="check"><input type="checkbox" checked={rights} onChange={e=>setRights(e.target.checked)}/> I own this media or have permission to process it.</label>
        {uploadPct!==null&&<div className="track"><div style={{width:`${uploadPct}%`}}/></div>}{uploadPct!==null&&<p className="tiny">Real bytes received: {uploadPct}%</p>}
        <div className="actions"><button className="primary" disabled={!file||!rights||busy} onClick={upload}>{busy?'Uploading / verifying…':'Import video'}</button>{busy&&<button className="outline" onClick={()=>{stop.current=true;cancel.current?.abort()}}>Pause upload</button>}</div>
      </div>:<div className="importContent"><h2>Import from YouTube</h2><p>Inspect a YouTube reference, then attach an authorized original video for processing. YouTube metadata alone cannot generate a clip.</p><div className="inputRow"><input placeholder="https://www.youtube.com/watch?v=..." value={yt} onChange={e=>setYt(e.target.value)}/><button className="primary" onClick={inspectYt}>Inspect link</button></div>{ytResult&&<p className="notice">{ytResult}</p>}<button className="textButton" onClick={()=>setPanel('upload')}>I have the original video →</button></div>}
    </section><section className="recent"><div className="sectionTitle"><h2>Recent projects</h2><span>{recent.length} sources</span></div>{recent.length?recent.map(m=><button className="recentItem" key={m.id} onClick={()=>openMedia(m)}><div className="thumb"><Film size={22}/></div><div><strong>{m.filename}</strong><p>{fmt(m.duration)} · {m.width} × {m.height} · {sizes(m.size)}</p></div><span className="open">Open →</span></button>):<p className="muted">No videos yet. Your projects will appear here after a successful upload.</p>}</section></> : <>
      <div className="breadcrumb"><button className="textButton" onClick={()=>{setActive(null);refresh();setJob(null)}}>← All projects</button><span>/</span><span>{active.filename}</span></div>
      <div className="studio"><div className="viewer"><video controls preload="metadata" playsInline src={`/api/media/${active.id}/stream`}/><div className="videoMeta"><strong>{active.filename}</strong><span>{fmt(active.duration)} · {active.width} × {active.height} · {sizes(active.size)}</span></div></div>
        <div className="settings"><div className="eyebrow">02 / INTELLIGENCE</div><h2>Find the best moments</h2><p>Real audiovisual analysis, not random scene changes.</p><label>Video category<select value={category} onChange={e=>setCategory(e.target.value)}>{['auto','gaming','podcast','livestream','education','drama','general'].map(x=><option key={x} value={x}>{x==='auto'?'Auto (general fallback)':x[0].toUpperCase()+x.slice(1)}</option>)}</select></label><label>Maximum clips<input type="number" min={1} max={12} value={maxClips} onChange={e=>setMaxClips(Number(e.target.value))}/></label><label className="check"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> Allow this video to be sent to the configured AI service for analysis.</label><button className="primary wide" onClick={analyze} disabled={!consent||Boolean(job&&!['done','failed','blocked','cancelled'].includes(job.status))}>Analyze actual footage</button><p className="tiny">If a model or permission is missing, analysis reports the blocker; manual editing still works.</p></div></div>
      {job&&<div className={`job ${job.status}`}><div><strong>{job.kind==='analyze'?'AI analysis':'Video rendering'} · {job.status.toUpperCase()}</strong><p>{job.error||job.stage}{job.status==='done'&&job.kind==='analyze'&&job.settings?.candidate_count===0?' — No worthwhile highlights were selected.':''}</p></div><div className="jobActions">{['queued','running'].includes(job.status)&&<button className="outline" onClick={async()=>setJob(await api(`/jobs/${job.id}/cancel`,{method:'POST'}))}>Cancel</button>}{['failed','blocked'].includes(job.status)&&<button className="outline" onClick={async()=>setJob(await api(`/jobs/${job.id}/retry`,{method:'POST'}))}><RefreshCcw size={15}/> Retry</button>}</div></div>}
      <section className="edit"><div className="sectionTitle"><div><div className="eyebrow">03 / CRAFT</div><h2>{editing?'Edit selected clip':'Build a manual clip'}</h2></div><span>Original audio ON · Extra effects OFF</span></div><p className="muted">Use precise source timecodes. Multiple segments render in the displayed order.</p><div className="segments">{segments.map((s,i)=><div className="seg" key={i}><span className="segNum">{String(i+1).padStart(2,'0')}</span><label>Start (sec)<input type="number" min={0} step="0.1" value={s.start} onChange={e=>setSegments(x=>x.map((z,k)=>k===i?{...z,start:Number(e.target.value)}:z))}/></label><label>End (sec)<input type="number" min={0} step="0.1" value={s.end} onChange={e=>setSegments(x=>x.map((z,k)=>k===i?{...z,end:Number(e.target.value)}:z))}/></label><div className="segmentActions"><button title="Move up" disabled={i===0} onClick={()=>swap(i,i-1)}><ArrowUp size={16}/></button><button title="Move down" disabled={i===segments.length-1} onClick={()=>swap(i,i+1)}><ArrowDown size={16}/></button><button title="Remove segment" disabled={segments.length===1} onClick={()=>setSegments(x=>x.filter((_,k)=>k!==i))}><Trash2 size={16}/></button></div></div>)}</div><button className="textButton" onClick={addSpan}><Plus size={16}/> Add a source segment</button><div className="options"><label>Clip name<input value={title} onChange={e=>setTitle(e.target.value)}/></label><label>Aspect ratio<select value={ratio} onChange={e=>setRatio(e.target.value)}>{['original','9:16','16:9','4:3','3:4','1:1'].map(x=><option key={x}>{x}</option>)}</select></label><label>Framing<select value={mode} onChange={e=>setMode(e.target.value)}><option value="fit">Fit — preserve full frame</option><option value="fill">Fill / crop</option></select></label><label>Quality<select value={quality} onChange={e=>setQuality(Number(e.target.value))}><option value={18}>Higher (CRF 18)</option><option value={20}>High (CRF 20)</option><option value={23}>Standard (CRF 23)</option><option value={26}>Smaller (CRF 26)</option></select></label></div><div className="actions"><button className="primary" onClick={saveClip}><Scissors size={17}/>{editing?'Save edit':'Create editable clip'}</button>{editing&&<button className="outline" onClick={()=>setEditing(null)}>Cancel edit</button>}</div></section>
      <section className="results"><div className="sectionTitle"><div><div className="eyebrow">04 / OUTPUT</div><h2>Clips & exports</h2></div><span>{clips.length} clips</span></div>{clips.length?clips.map(c=><article className="clip" key={c.id}><div className="clipVisual">{c.rendered?<video controls playsInline preload="metadata" src={`/api/clips/${c.id}/preview`}/>:<div className="pending"><Play size={28}/><span>Render to preview an actual MP4</span></div>}</div><div className="clipText"><div className="clipTop"><strong>{c.title}</strong><span>{fmt(c.duration)}</span></div><p>{c.origin==='manual'?'Manually selected':'AI suggestion — inspect before publishing'}</p><p className="why">{c.reasoning}</p><div className="actions"><button className="outline" onClick={()=>editClip(c)}><Scissors size={16}/> Edit</button><button className="primary" onClick={()=>exportClip(c.id)}><Film size={16}/> {c.rendered?'Re-render':'Render MP4'}</button>{c.rendered&&<a className="download" href={`/api/clips/${c.id}/download`}><Download size={16}/> Download</a>}</div></div></article>):<p className="muted">No clips yet. Analyze the source or create a manual edit above.</p>}</section>
      </>}
      <footer>CLIPRA AI NEXT · Real source files · Real FFmpeg exports · AI requires a verified provider</footer>
    </main></div>;
}