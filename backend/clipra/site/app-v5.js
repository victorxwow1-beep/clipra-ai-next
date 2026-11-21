'use strict';
// CLIPRA v5: compact, mobile-first first-party control surface.
// This UI is connected to the existing authenticated FastAPI + FFmpeg backend.
const root=document.getElementById('app');
const state={logged:false,view:'home',tab:'upload',sourceFile:null,yt:'',rights:false,
count:'auto',customCount:5,length:'24',customMinutes:0,customSeconds:24,
category:'auto',ratio:'9:16',mode:'fit',quality:'18',busy:false,
uploadPercent:null,job:null,statusText:'',error:'',notice:'',
media:[],selected:null,clips:[],editing:null,editSegments:[],editTitle:''};
const Q=(v)=>String(v==null?'':v).replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const format=(v)=>{const n=Math.max(0,Math.floor(Number(v)||0));return Math.floor(n/3600)>0?Math.floor(n/3600)+':'+String(Math.floor(n%3600/60)).padStart(2,'0')+':'+String(n%60).padStart(2,'0'):Math.floor(n/60)+':'+String(n%60).padStart(2,'0')};
const size=(v)=>((Number(v)||0)/1048576).toFixed(1)+' MB';
const body=(v)=>JSON.stringify(v);
const choices=(id,data,current)=>'<select id="'+id+'" class="field" aria-label="'+id+'">'+data.map(x=>'<option value="'+Q(x[0])+'" '+(String(x[0])===String(current)?'selected':'')+'>'+Q(x[1])+'</option>').join('')+'</select>';
async function api(path,opts={}){
 const res=await fetch('/api'+path,{credentials:'same-origin',cache:'no-store',...opts,headers:{...(opts.body?{'Content-Type':'application/json'}:{}),...(opts.headers||{})}});
 if(!res.ok){let message='Request failed (HTTP '+res.status+')';try{const data=await res.json();message=typeof data.detail==='string'?data.detail:JSON.stringify(data.detail||data)}catch{}throw Error(message)}
 return res.status===204?null:res.json();
}
const post=(path,data)=>api(path,{method:'POST',body:body(data)});
function loading(){return '<div class="wait" aria-live="polite"><i class="spinner"></i> '+Q(state.statusText||'Processing video…')+'</div>'}
function message(){return (state.error?'<aside class="notice bad" role="alert">'+Q(state.error)+' <button data-action="dismiss" class="close">×</button></aside>':'')+(state.notice?'<aside class="notice" role="status">'+Q(state.notice)+'</aside>':'')}
function shell(inner){
 return '<header class="head"><div class="logo"><span>◈</span><strong>CLIPRA</strong><small>VIDEO STUDIO</small></div><button data-action="logout" class="ghost" aria-label="Sign out">Sign out</button></header>'+
 '<main class="stage">'+message()+inner+'</main><footer>Original recordings stay unchanged · Your clips use real MP4 export · No Higgsfield credits</footer>';
}
function login(){
 root.innerHTML='<main class="login"><form id="loginForm" class="sign"><div class="logo"><span>◈</span><strong>CLIPRA</strong></div><h1>Your video studio</h1><p>Private workspace sign-in. No AI credits required.</p>'+message()+
 '<label class="label" for="password">Workspace password</label><input id="password" type="password" autocomplete="current-password" required class="field">'+
 '<button class="primary full" type="submit">Open CLIPRA</button></form></main>';
}
function sourceControl(){
 if(state.tab==='youtube')return '<label class="label" for="yt">YouTube video or LIVE link</label>'+
  '<input class="field" id="yt" type="url" inputmode="url" placeholder="https://youtube.com/watch?v=..." value="'+Q(state.yt)+'">'+
  '<p class="hint">For your own or authorized public footage. Some live/private videos cannot be imported by this host; file upload remains available.</p>';
 return '<label class="filepicker" for="file"><span class="icon-big">↑</span><strong>'+(state.sourceFile?Q(state.sourceFile.name):'Choose a video')+'</strong>'+
  '<small>'+(state.sourceFile?size(state.sourceFile.size)+' selected':'From Gallery or Files · MP4, MOV, WebM, MKV')+'</small></label>'+
  '<input id="file" type="file" accept="video/*,.mp4,.mov,.mkv,.webm,.avi,.m4v" class="sr-only" aria-label="Choose a video">'+
  (state.sourceFile?'<button class="textbtn" data-action="clearFile">Change selection</button>':'');
}
function home(){
 const countChoices=[['auto','Auto · Best only'],['3','3 clips'],['5','5 clips'],['10','10 clips'],['custom','Custom']];
 const lenChoices=[['15','15 sec'],['24','24 sec'],['30','30 sec'],['60','60 sec'],['custom','Custom time']];
 const cats=[['auto','Auto detect'],['gaming','Gaming'],['podcast','Podcast'],['funny','Funny'],['education','Educational'],['livestream','Livestream']];
 const recent=state.media.slice(0,6).map(x=>'<button data-action="open" data-id="'+Q(x.id)+'" class="recent"><span class="recentmark">▶</span><span><strong>'+Q(x.filename)+'</strong><small>'+format(x.duration)+' · '+size(x.size)+'</small></span><b>View ›</b></button>').join('');
 const upload = state.uploadPercent!==null?'<div class="progress"><div style="width:'+Math.min(100,state.uploadPercent)+'%"></div></div><small class="hint">'+state.uploadPercent+'% uploaded · resume supported on reconnect</small>':'';
 const status=state.job?'<div class="jobstate"><strong>'+Q(state.job.kind==='youtube_import'?'Importing video':state.job.kind==='smart'?'Checking video moments':'Processing')+' · '+Q(state.job.status)+'</strong><p>'+Q(state.job.error||state.job.stage||'Working on your video')+'</p></div>':'';
 return shell('<section class="intro"><h1>Turn videos into clips.</h1><p>Choose a video, set your clips, and start.</p></section>'+
 '<section class="workspace"><div class="step"><span>01</span><h2>Choose your video</h2></div>'+
 '<div class="tabs"><button data-action="tabUpload" class="'+(state.tab==='upload'?'active':'')+'">↑ Gallery / Files</button><button data-action="tabYoutube" class="'+(state.tab==='youtube'?'active':'')+'">▷ YouTube Link</button></div>'+
 '<div class="source">'+sourceControl()+'</div>'+
 '<label class="rights"><input id="rights" type="checkbox" '+(state.rights?'checked':'')+'>I own this recording or have permission to edit it.</label>'+
 '<div class="step two"><span>02</span><h2>Set your clips</h2></div>'+
 '<div class="settings"><label class="setting"><b>How many clips?</b>'+choices('count',countChoices,state.count)+'</label>'+
 '<label class="setting"><b>Length per clip</b>'+choices('length',lenChoices,state.length)+'</label>'+
 '<label class="setting"><b>Video type</b>'+choices('category',cats,state.category)+'</label>'+
 '<label class="setting"><b>Format</b>'+choices('ratio',[['9:16','Shorts · 9:16'],['original','Original'],['16:9','Wide · 16:9'],['4:3','4:3'],['1:1','Square']],state.ratio)+'</label></div>'+
 (state.count==='custom'?'<div class="custom"><label class="setting"><b>Number of clips (1–12)</b><input id="customCount" type="number" min="1" max="12" value="'+Q(state.customCount)+'" class="field"></label></div>':'')+
 (state.length==='custom'?'<div class="custom custom-time"><label class="setting"><b>Minutes</b><input id="customMinutes" class="field" type="number" min="0" max="30" value="'+Q(state.customMinutes)+'"></label><label class="setting"><b>Seconds</b><input id="customSeconds" class="field" type="number" min="0" max="59" value="'+Q(state.customSeconds)+'"></label></div>':'')+
 '<details class="advanced"><summary>More options (optional)</summary><div class="settings"><label class="setting"><b>Quality</b>'+choices('quality',[['18','Highest · larger file'],['20','High quality'],['23','Standard · smaller file']],state.quality)+'</label>'+
 '<label class="setting"><b>Video framing</b>'+choices('mode',[['fit','Fit · keep full picture'],['fill','Fill · crop edges']],state.mode)+'</label></div></details>'+
 '<button class="primary full big" data-action="find" '+(state.busy?'disabled':'')+'>'+ (state.busy?'Working…':'✦ Find Best Clips')+'</button>'+
 upload+status+(state.busy?loading():'')+
 '<p class="smallprint">Free local analysis checks evidence in the real source. Spoken clips use open-source Whisper; gaming uses on-screen evidence. Full visual AI is not verified on this host, so we will not invent highlights.</p>'+
 '</section>'+
 '<section class="previous"><div class="rowhead"><h2>Your videos</h2><span>'+state.media.length+'</span></div>'+
 (recent||'<p class="hint">Your imported videos will appear here.</p>')+'</section>');
}
function clipCard(c,index){
 const d=format(c.duration);
 const src=c.rendered?'<video controls playsinline preload="metadata" src="/api/clips/'+Q(c.id)+'/preview"></video>':
 '<div class="preview-empty"><span>▷</span><small>Rendering video clip…</small></div>';
 const why=c.origin==='local_speech'?'Based on original spoken words':c.origin==='local_text_evidence'?'Based on visible in-game text':c.origin==='manual'?'Your manual selection':'Source-grounded suggestion';
 return '<article class="clipcard"><div class="thumb">'+src+'</div><div class="clipdetails"><div class="clipheading"><h3>'+Q(c.title||'Clip '+(index+1))+'</h3><span>'+d+'</span></div>'+
 '<p class="hint">'+Q(why)+'</p>'+
 '<details class="why"><summary>Why this clip?</summary><p>'+Q(c.reasoning||'Manually selected. Please review.')+'</p></details>'+
 '<div class="clipactions"><button class="outline" data-action="edit" data-id="'+Q(c.id)+'">Edit</button>'+
 '<button class="outline reject" data-action="reject" data-id="'+Q(c.id)+'">Reject</button>'+
 (c.rendered?'<a class="primary compact" href="/api/clips/'+Q(c.id)+'/download" download>Download MP4</a>':
 '<button class="primary compact" data-action="renderOne" data-id="'+Q(c.id)+'">Render MP4</button>')+
 '</div></div></article>';
}
function editPanel(){
 const c=state.clips.find(x=>x.id===state.editing);
 if(!c)return '';
 const fields=state.editSegments.map((seg,i)=>'<div class="timegrid"><label class="setting"><b>Start (seconds)</b><input class="field" data-segment="'+i+'" data-bound="start" type="number" step="0.1" min="0" value="'+Q(seg.start)+'"></label>'+
 '<label class="setting"><b>End (seconds)</b><input class="field" data-segment="'+i+'" data-bound="end" type="number" step="0.1" min="0" value="'+Q(seg.end)+'"></label></div>').join('');
 return '<section class="editpanel"><h2>Edit selected clip</h2><label class="setting"><b>Title</b><input class="field" id="editTitle" value="'+Q(state.editTitle)+'"></label>'+fields+
 '<div class="clipactions"><button class="primary" data-action="saveEdit">Save & render</button><button class="outline" data-action="cancelEdit">Cancel</button></div></section>';
}
function studio(){
 const m=state.selected;
 if(!m)return home();
 const allRendered=state.clips.length>0&&state.clips.every(c=>c.rendered);
 const clips=state.clips.map(clipCard).join('');
 const status=state.job?'<div class="jobstate"><strong>'+Q(state.job.kind==='smart'?'Finding highlights':state.job.kind==='render'?'Rendering MP4 clips':'Processing')+' · '+Q(state.job.status)+'</strong>'+
 '<p>'+Q(state.job.error||state.job.stage||'Working on your video')+'</p></div>':'';
 const noClips=!state.busy&&!state.clips.length?'<div class="empty"><h3>No verified clips yet</h3><p>The free model may find no strong moments. It will not create random clips just to reach your requested count.</p>'+
 '<div class="clipactions"><button data-action="manual" class="outline">Create manual clip</button><button data-action="rerun" class="outline">Analyze again</button></div></div>':'';
 return shell('<div class="studiohead"><button data-action="home" class="ghost">← Back</button><span>Review & export</span></div>'+
 '<div class="vidinfo"><div class="vidmeta"><h1>'+Q(m.filename)+'</h1><small>'+format(m.duration)+' · '+m.width+' × '+m.height+' · '+size(m.size)+'</small></div>'+
 '<video controls playsinline preload="metadata" src="/api/media/'+Q(m.id)+'/stream"></video></div>'+
 status+(state.busy?loading():'')+
 '<div class="rowhead"><h2>Your clips</h2><span>'+state.clips.length+' clips</span></div>'+
 '<div class="tools">'+(allRendered?'<a class="primary" href="/api/media/'+Q(m.id)+'/download-all" download>↓ Download All ZIP</a>':
 '<button data-action="renderAll" class="primary" '+(!state.clips.length||state.busy?'disabled':'')+'>Render all MP4s</button>')+
 '<button data-action="manual" class="outline">+ Manual cut</button><button data-action="rerun" class="outline" '+(state.busy?'disabled':'')+'>Find more</button></div>'+
 editPanel()+clips+noClips+
 '<p class="smallprint">Review every clip before publishing. Cropping and re-encoding affect the output; original media is unchanged.</p>');
}
function paint(){if(!state.logged)login();else root.innerHTML=state.view==='studio'?studio():home()}
function setError(e){state.error=String(e&&e.message||e);state.notice='';state.busy=false;state.uploadPercent=null;paint()}
function clearError(){state.error='';state.notice=''}
async function refreshMedia(){
 state.media=await api('/media');
 if(state.selected){
  const m=state.media.find(x=>x.id===state.selected.id);
  if(m)state.selected=m;
 }
 if(state.selected)state.clips=await api('/media/'+state.selected.id+'/clips');
}
const pause=(ms)=>new Promise(resolve=>setTimeout(resolve,ms));
function updateJob(j){state.job=j;const el=document.querySelector('.jobstate');if(el){const tag=el.querySelector('strong');const txt=el.querySelector('p');if(tag)tag.textContent=(j.kind==='smart'?'Finding highlights':j.kind==='render'?'Rendering clips':'Importing')+' · '+j.status;if(txt)txt.textContent=j.error||j.stage||'Processing';}else paint()}
async function monitorJob(j){
 updateJob(j);
 const start=Date.now();
 while(!['done','failed','blocked','cancelled'].includes(j.status)){
  await pause(1600);j=await api('/jobs/'+j.id);updateJob(j);
  if(Date.now()-start>2*60*60*1000)throw Error('The job exceeded the two-hour progress window. Check the source again.');
 }
 if(j.status!=='done')throw Error(j.error||'The video processing job '+j.status+'. Please review the failure and retry.');
 return j;
}
function count(){return state.count==='auto'?5:state.count==='custom'?Number(state.customCount):Number(state.count)}
function length(){return state.length==='custom'?Number(state.customMinutes)*60+Number(state.customSeconds):Number(state.length)}
function settings(){
 const n=count(), t=length();
 if(!Number.isInteger(n)||n<1||n>12)throw Error('Choose between 1 and 12 clips.');
 if(!Number.isFinite(t)||t<5||t>1800)throw Error('Clip length must be between 5 seconds and 30 minutes.');
 return {category:state.category,max_clips:n,length_seconds:t,ratio:state.ratio,mode:state.mode,crf:Number(state.quality)};
}
async function startSmart(){
 if(!state.selected)throw Error('Import a video first');
 const req=settings();
 state.view='studio';state.busy=true;state.statusText='Checking original video and audio…';paint();
 const j=await post('/media/'+state.selected.id+'/smart',req);
 const finished=await monitorJob(j);
 await refreshMedia();
 state.busy=false;
 state.notice=(finished.settings&&finished.settings.candidate_count===0)?
 'No source-backed highlights were found. Your original recording remains available.':'Found '+state.clips.length+' clip suggestions. Review the results.';
 paint();
 if(state.clips.length){await renderAll(true)}
}
async function uploadFile(){
 const f=state.sourceFile;
 if(!f)throw Error('Choose a video from your phone first.');
 const key='clipra-upload:'+f.name+':'+f.size+':'+f.lastModified;
 let record=null;try{record=JSON.parse(localStorage.getItem(key)||'null')}catch{}
 let uploadId=record&&record.id;let offset=0;
 if(uploadId){
  const head=await fetch('/api/uploads/'+uploadId,{method:'HEAD',credentials:'same-origin'});
  if(head.ok)offset=Number(head.headers.get('Upload-Offset')||0);
  else uploadId=null;
 }
 if(!uploadId){const result=await post('/uploads',{filename:f.name,size:f.size,rights_confirmed:true});uploadId=result.id;localStorage.setItem(key,JSON.stringify({id:uploadId}));}
 while(offset<f.size){
  let retries=0;
  while(true){
   try{
    const res=await fetch('/api/uploads/'+uploadId,{method:'PATCH',credentials:'same-origin',headers:{'Upload-Offset':String(offset),'Tus-Resumable':'1.0.0','Content-Type':'application/offset+octet-stream'},body:f.slice(offset,offset+4*1048576)});
    if(!res.ok){let reason='Upload HTTP '+res.status;try{const j=await res.json();reason=j.detail||reason}catch{}throw Error(reason)}
    const next=Number(res.headers.get('Upload-Offset')||0);
    if(next<=offset)throw Error('Upload did not advance');
    offset=next;break;
   }catch(e){
    retries++;
    if(retries>3)throw Error('Upload paused at '+Math.round(offset/f.size*100)+'%. Choose the same file to resume. '+String(e.message||e));
    const head=await fetch('/api/uploads/'+uploadId,{method:'HEAD',credentials:'same-origin'});
    if(head.ok)offset=Number(head.headers.get('Upload-Offset')||offset);
    await pause(retries*600);
   }
  }
  state.uploadPercent=Math.round(offset/f.size*100);
  const bar=document.querySelector('.progress > div');if(bar)bar.style.width=state.uploadPercent+'%';
  const small=document.querySelector('.progress + .hint');if(small)small.textContent=state.uploadPercent+'% uploaded · resume supported';
 }
 const imported=await api('/uploads/'+uploadId+'/complete',{method:'POST'});
 localStorage.removeItem(key);
 state.sourceFile=null;state.uploadPercent=null;state.selected=imported;
 await refreshMedia();await startSmart();
}
async function find(){
 if(state.busy)return;
 clearError();settings();
 if(!state.rights)throw Error('Please confirm you own the recording or have permission to edit it.');
 if(state.tab==='upload'&&!state.sourceFile)throw Error('Choose a video from Gallery / Files.');
 if(state.tab==='youtube'&&!state.yt.trim())throw Error('Paste your YouTube video or LIVE link.');
 state.busy=true;state.statusText=state.tab==='upload'?'Uploading original video in small chunks…':'Importing authorized YouTube source…';paint();
 if(state.tab==='upload'){await uploadFile();return}
 const queued=await post('/youtube/import',{url:state.yt,rights_confirmed:true});
 await monitorJob(queued);
 const imported=(await api('/media/'+queued.media_id));
 state.selected=imported;await refreshMedia();await startSmart();
}
async function openMedia(id){clearError();state.selected=state.media.find(x=>x.id===id)||await api('/media/'+id);state.clips=await api('/media/'+id+'/clips');state.job=null;state.view='studio';paint()}
async function renderAll(silent=false){
 if(!state.selected)throw Error('No video selected.');
 const remaining=state.clips.filter(c=>!c.rendered);
 if(!remaining.length){state.busy=false;paint();return}
 state.busy=true;state.statusText='Creating downloadable MP4 clips…';if(!silent)clearError();paint();
 let last=null;
 for(const c of remaining)last=await api('/clips/'+c.id+'/render',{method:'POST'});
 if(last)await monitorJob(last);
 await refreshMedia();state.busy=false;state.statusText='';paint();
}
async function renderOne(id){state.busy=true;state.statusText='Rendering selected clip…';paint();await monitorJob(await api('/clips/'+id+'/render',{method:'POST'}));await refreshMedia();state.busy=false;paint()}
async function editClip(id){const c=state.clips.find(x=>x.id===id);if(!c)return;state.editing=id;state.editTitle=c.title;state.editSegments=c.segments.map(s=>({...s}));paint();document.querySelector('.editpanel')?.scrollIntoView({block:'start',behavior:'smooth'})}
async function saveEdit(){
 const c=state.clips.find(x=>x.id===state.editing);if(!c)throw Error('Select a clip to edit');
 const segments=state.editSegments.map(x=>({start:Number(x.start),end:Number(x.end)}));
 if(segments.some(x=>!Number.isFinite(x.start)||!Number.isFinite(x.end)||x.start<0||x.end<=x.start||x.end>state.selected.duration+.025))throw Error('Check the start/end seconds of each cut.');
 const data={title:state.editTitle||'Edited clip',segments,ratio:c.options?.ratio||state.ratio,mode:c.options?.mode||state.mode,crf:c.options?.crf||Number(state.quality)};
 await api('/clips/'+c.id,{method:'PUT',body:body(data)});
 const id=c.id;state.editing=null;await refreshMedia();await renderOne(id);
}
async function reject(id){if(!confirm('Reject this clip? You can analyze again later.'))return;await api('/clips/'+id,{method:'DELETE'});await refreshMedia();paint()}
async function manual(){
 const dur=Math.min(state.selected.duration,length()),c=await post('/media/'+state.selected.id+'/clips',{title:'My manual cut',segments:[{start:0,end:dur}],ratio:state.ratio,mode:state.mode,crf:Number(state.quality)});
 await refreshMedia();await editClip(c.id)
}
async function execute(action,btn){
 const id=btn.dataset.id;
 switch(action){
 case 'dismiss':state.error='';paint();break;
 case 'logout':await api('/auth/logout',{method:'POST'});state.logged=false;state.view='home';paint();break;
 case 'tabUpload':state.tab='upload';clearError();paint();break;
 case 'tabYoutube':state.tab='youtube';clearError();paint();break;
 case 'clearFile':state.sourceFile=null;paint();break;
 case 'find':await find();break;
 case 'open':await openMedia(id);break;
 case 'home':state.view='home';state.job=null;await refreshMedia();paint();break;
 case 'renderAll':await renderAll();break;
 case 'renderOne':await renderOne(id);break;
 case 'edit':await editClip(id);break;
 case 'cancelEdit':state.editing=null;paint();break;
 case 'saveEdit':await saveEdit();break;
 case 'reject':await reject(id);break;
 case 'manual':await manual();break;
 case 'rerun':clearError();await startSmart();break;
 }
}
root.addEventListener('click',async(e)=>{const btn=e.target.closest('[data-action]');if(!btn)return;try{await execute(btn.dataset.action,btn)}catch(err){setError(err)}});
root.addEventListener('change',(e)=>{
 const el=e.target;
 if(el.id==='file'){state.sourceFile=el.files&&el.files[0]||null;paint();return}
 if(el.id==='rights'){state.rights=el.checked;return}
 if(['count','length','category','ratio','mode','quality'].includes(el.id)){state[el.id]=el.value;paint();return}
});
root.addEventListener('input',(e)=>{
 const el=e.target;
 if(['yt','customCount','customMinutes','customSeconds'].includes(el.id))state[el.id]=el.value;
 if(el.id==='editTitle')state.editTitle=el.value;
 if(el.dataset.segment!==undefined){const index=Number(el.dataset.segment);if(state.editSegments[index])state.editSegments[index][el.dataset.bound]=Number(el.value)}
});
root.addEventListener('submit',async(e)=>{
 if(e.target.id!=='loginForm')return;e.preventDefault();
 try{await post('/auth/login',{password:document.getElementById('password').value});state.logged=true;clearError();await refreshMedia();paint()}catch(err){setError(err)}
});
(async()=>{try{await api('/me');state.logged=true;await refreshMedia()}catch{state.logged=false}paint()})();
