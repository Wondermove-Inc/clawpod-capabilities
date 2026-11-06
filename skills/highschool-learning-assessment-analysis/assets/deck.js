<script>
/* ===========================================
   SLIDE PRESENTATION CONTROLLER
   Keyboard: ArrowRight/ArrowDown/Space/PageDown = next, ArrowLeft/ArrowUp/PageUp = prev, Home/End.
   Also swipe, mouse wheel, nav dots and #N URL hash (e.g. #3).
   =========================================== */
class SlidePresentation{
 constructor(){
  this.slides=[...document.querySelectorAll('.slide')];this.stage=document.getElementById('deckStage');
  this.cur=0;this.lock=false;this.bar=document.querySelector('.progress');this.dots=document.querySelector('.deck-controls');
  this.slides.forEach((_,i)=>{const b=document.createElement('button');b.setAttribute('aria-label',(i+1)+'번 슬라이드');b.onclick=()=>this.go(i);this.dots.appendChild(b);});
  this.scale();addEventListener('resize',()=>this.scale());
  this.keys();this.touch();this.wheel();
  const h=parseInt(location.hash.slice(1),10);this.go(isNaN(h)?0:h-1);
  addEventListener('hashchange',()=>{const n=parseInt(location.hash.slice(1),10);if(!isNaN(n))this.go(n-1);});
 }
 scale(){const k=Math.min(innerWidth/1920,innerHeight/1080);
  this.stage.style.transform=`translate(${(innerWidth-1920*k)/2}px,${(innerHeight-1080*k)/2}px) scale(${k})`;}
 keys(){document.addEventListener('keydown',e=>{
  if(e.target.isContentEditable)return;
  if(['ArrowRight','ArrowDown','PageDown',' ','Spacebar'].includes(e.key)){e.preventDefault();this.go(this.cur+1);}
  else if(['ArrowLeft','ArrowUp','PageUp'].includes(e.key)){e.preventDefault();this.go(this.cur-1);}
  else if(e.key==='Home')this.go(0);else if(e.key==='End')this.go(this.slides.length-1);});}
 touch(){let x=null;addEventListener('touchstart',e=>{x=e.touches[0].clientX},{passive:true});
  addEventListener('touchend',e=>{if(x===null)return;const d=e.changedTouches[0].clientX-x;if(Math.abs(d)>50)this.go(this.cur+(d<0?1:-1));x=null;});}
 wheel(){addEventListener('wheel',e=>{if(this.lock||Math.abs(e.deltaY)<30)return;this.lock=true;this.go(this.cur+(e.deltaY>0?1:-1));setTimeout(()=>this.lock=false,700);},{passive:true});}
 go(i){this.cur=Math.max(0,Math.min(i,this.slides.length-1));
  this.slides.forEach((s,j)=>{s.classList.toggle('active',j===this.cur);s.classList.toggle('visible',j===this.cur);});
  [...this.dots.children].forEach((b,j)=>b.classList.toggle('on',j===this.cur));
  this.bar.style.width=((this.cur+1)/this.slides.length*100)+'%';
  if(location.hash!=='#'+(this.cur+1))history.replaceState(null,'','#'+(this.cur+1));}
}
const deck=new SlidePresentation();

/* ===========================================
   INLINE EDITING — hover top-left corner or press E; edits auto-save to localStorage
   =========================================== */
const editor={isActive:false,key:'hakpyeong-dark-keynote-edits',
 targets(){return document.querySelectorAll('.slide h1,.slide h2,.slide p,.slide b,.slide span,.slide td,.slide li,.slide .n,.slide .k,.slide .act,.slide .meta')},
 toggleEditMode(){this.isActive=!this.isActive;document.body.classList.toggle('editing',this.isActive);
  document.getElementById('editToggle').classList.toggle('active',this.isActive);
  document.getElementById('editToggle').textContent=this.isActive?'편집 끝내기':'편집';
  this.targets().forEach(el=>el.contentEditable=this.isActive?'true':'false');if(!this.isActive)this.save();},
 save(){const d={};this.targets().forEach((el,i)=>d[i]=el.innerHTML);try{localStorage.setItem(this.key,JSON.stringify(d))}catch(e){}},
 load(){try{const d=JSON.parse(localStorage.getItem(this.key)||'null');if(!d)return;this.targets().forEach((el,i)=>{if(d[i]!==undefined)el.innerHTML=d[i]})}catch(e){}},
 exportFile(){this.save();const c=document.documentElement.cloneNode(true);c.querySelectorAll('[contenteditable]').forEach(e=>e.removeAttribute('contenteditable'));
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['<!DOCTYPE html>\n'+c.outerHTML],{type:'text/html'}));a.download='학평분석-다크키노트-edited.html';a.click();}};
editor.load();
document.getElementById('editToggle').addEventListener('click',()=>editor.toggleEditMode());
const hotzone=document.querySelector('.edit-hotzone'),editToggle=document.getElementById('editToggle');let hideTimeout=null;
hotzone.addEventListener('mouseenter',()=>{clearTimeout(hideTimeout);editToggle.classList.add('show')});
hotzone.addEventListener('mouseleave',()=>{hideTimeout=setTimeout(()=>{if(!editor.isActive)editToggle.classList.remove('show')},400)});
editToggle.addEventListener('mouseenter',()=>clearTimeout(hideTimeout));
editToggle.addEventListener('mouseleave',()=>{hideTimeout=setTimeout(()=>{if(!editor.isActive)editToggle.classList.remove('show')},400)});
hotzone.addEventListener('click',()=>editor.toggleEditMode());
document.addEventListener('keydown',e=>{
 if((e.key==='e'||e.key==='E')&&!e.target.isContentEditable){editor.toggleEditMode();}
 if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();editor.exportFile();}});
document.addEventListener('input',()=>editor.save());
</script>