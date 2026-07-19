/* ============================================================================
 * behavior.js - shared component behavior for the AWL Multi-Agent Dashboard.
 *
 * SINGLE SOURCE OF TRUTH for interaction logic, loaded by mockup.html (same
 * design/ directory). Extracted verbatim from mockup.html's inline behavior
 * block. (Until 2026-07-05 it was also loaded by the interactive catalog
 * gallery.html — retired; its frozen snapshot under
 * archive/design/design-v12p7-gallery-retirement/ carries its own copy.)
 *
 * The ONLY semantic change vs the original inline block: boot() early-returns
 * when there is no .app root, so it is inert on any page that isn't the
 * mockup. The shared dismiss/Escape/hover-card listeners auto-install
 * unconditionally by design.
 * ========================================================================== */

  /* ===== Lucide render helper (UI icons) ===== */
  function LU(){ if(window.lucide&&lucide.createIcons) lucide.createIcons({attrs:{'stroke-width':2.25}}); }

  /* ===== tabs ===== */
  function switchTab(g,t){
    /* v1.2: remap stale stored doc tabs (the old Readme/Claude/Todo tabs folded into "Documents").
       Gate on the known tab set — NOT getElementById('doc-'+t), which since ND-L1 also matches the
       doc CARD ids (doc-readme, doc-claude, …) and would leave the remap dead for those stale keys. */
    if(g==='doc'&&['plan','documents','assets'].indexOf(t)<0){t={readme:'documents',claude:'documents',todo:'documents'}[t]||'plan';}
    /* remap stale internal tab keys to the user-facing names (requests→inbox, library→templates) */
    if(g==='mid'&&t==='past')t='details';   /* NU-2: the Past tab left the mid bar for the Team panel's Past drawer — a stale stored mid:'past' (persisted below, replayed at boot) would otherwise blank the whole Agent panel */
    if(g==='feed'&&t==='requests')t='inbox';
    if(g==='feed'&&t==='messages')t='transcript';   /* ND 6a: the Messages tab is renamed Transcript — remap stale stored keys + old callers */
    if(g==='prompt'&&(t==='templates'||t==='library'))t='compose';   /* v10p1 #22: Templates folded into Compose */
    document.querySelectorAll('[data-group="'+g+'"]').forEach(p=>p.classList.add('hidden'));
    const pane=document.getElementById(g+'-'+t); if(pane)pane.classList.remove('hidden');
    document.querySelectorAll('[data-tab-group="'+g+'"]').forEach(b=>b.classList.toggle('active',b.dataset.tab===t));
    const foots=document.querySelectorAll('[data-group="'+g+'-foot"]');
    if(foots.length){foots.forEach(f=>f.classList.add('hidden'));const fm=document.getElementById(g+'-foot-'+t);if(fm)fm.classList.remove('hidden');}
    if(g==='prompt'){
      const ar=document.getElementById('prompt-actions'); if(ar)ar.classList.toggle('hidden',t==='history');
      const rv=document.getElementById('revise-split'); if(rv)rv.classList.toggle('hidden',t!=='compose');
      const ha=document.getElementById('prompt-history-actions'); if(ha)ha.classList.toggle('hidden',t!=='history');
      /* Next-up item 9: the From column forks per tab — Compose keeps the single-select SOURCE (#source-dd),
         History swaps it for the multi-select From FILTER (#hist-from — the To list minus Scratch). */
      const sf=document.getElementById('source-dd'); if(sf)sf.classList.toggle('hidden',t==='history');
      const hf=document.getElementById('hist-from'); if(hf)hf.classList.toggle('hidden',t!=='history');
      if(t==='history'&&typeof eaUpdate==='function')eaUpdate('hist');   /* R-batch items 6a/7: re-gate History's link-dd + Output Export for the current selection */
    }
    const s=JSON.parse(localStorage.getItem('awl-v8')||'{}');s[g]=t;localStorage.setItem('awl-v8',JSON.stringify(s));
    if(typeof refreshJumpPills==='function')setTimeout(refreshJumpPills,30);   /* A12/A3: a revealed scroll region needs its pills (re)evaluated once it has a real height */
    if(g==='feed'){ const ma=document.getElementById('feed-actions'); if(ma)ma.classList.remove('hidden');
      const sb=document.getElementById('summary-btn'); if(sb)sb.classList.toggle('hidden',!(t==='transcript'||t==='scratch'||t==='log'));   /* v1.x #7: Summarize available on Transcript + Scratch + Log */
      const stp=document.getElementById('tx-stop-btn'); if(stp)stp.classList.toggle('hidden',t!=='transcript');   /* v1.x #6: Stop only on the Transcript */
      const sa=document.getElementById('feed-selall-btn'); if(sa)sa.classList.remove('hidden');   /* G2: select/deselect-all on every feed tab */
      const ov=document.getElementById('feed-summary'); if(ov)ov.classList.remove('open'); if(sb)sb.classList.remove('active');   /* close any open summary when switching feed tabs */
      if(typeof eaUpdate==='function')eaUpdate('feed');   /* R-batch items 6a/7: re-gate the feed link-dd + Output Export for the now-active tab's selection */
      drawEdgesSoon(); }
    if(typeof syncEditorMics==='function')setTimeout(syncEditorMics,0);   /* L: switching Compose↔History / Plans↔Documents re-evaluates each mic's field visibility (let the revealed pane settle first) */
  }
  /* ===== generic interactions (ported from v7p3) ===== */
  /* NU-2: toggleDrawer(which) drives BOTH Team-panel drawers — 'link' (#link-drawer, the default so the old
     no-arg call sites keep working: the drawer's close x, linkSave/linkDelete) and 'past' (#past-drawer).
     The two occupy the same absolute slot in #pRight (z-30), so opening one closes the other. */
  function toggleDrawer(which){const id=which==='past'?'past-drawer':'link-drawer';const el=document.getElementById(id);if(!el)return;
    if(el.classList.contains('hidden')){const other=document.getElementById(id==='past-drawer'?'link-drawer':'past-drawer');if(other)other.classList.add('hidden');}
    el.classList.toggle('hidden');}
  function agSync(scope){const link=scope.querySelector('[data-allnone]');if(!link)return;const rows=[...scope.querySelectorAll('.agrow')];const allOn=rows.length>0&&rows.every(r=>r.classList.contains('on'));link.dataset.act=allOn?'none':'all';link.textContent=allOn?'None':'All';}  /* show only the useful action */
  function toggleAgRow(el){el.classList.toggle('on');
    if(el.classList.contains('agrow--parent')){const subs=el.nextElementSibling;const on=el.classList.contains('on');   /* parent select = the whole subtree (parent + its subagents) */
      if(subs&&subs.classList.contains('agrow-subs'))subs.querySelectorAll('.agrow--sub').forEach(r=>r.classList.toggle('on',on));}
    const sc=el.closest('[data-agscope]');if(sc){agSync(sc);updateAgBadges(sc);updateSubCounts(sc);if(sc.id==='hist-from'&&typeof applyHistFilters==='function')applyHistFilters();}}   /* multi-select (Target / Filter); item 7 recount + item 9 History-From filter */
  function toggleAgSubs(e,btn){e.stopPropagation();const row=btn.closest('.agrow');if(!row)return;const subs=row.nextElementSibling;if(!subs||!subs.classList.contains('agrow-subs'))return;const open=subs.classList.toggle('open');row.classList.toggle('subs-open',open);}   /* expand/collapse a parent's subagent sub-rows (does NOT change selection) */
  function setFeedSubFilter(node,id){const fil=document.getElementById('feed-filter');if(!fil)return false;   /* scope the Feed filter to one subagent (called by subBadgeClick) */
    const key=node?agKeyFromNode(node):'';   /* Next-up item 6: sub ids repeat across parents (every run starts at A1), so scope the lookup to the clicked card's agent (rows carry data-par from the shared roster) */
    const sub=[...fil.querySelectorAll('.agrow--sub')].find(r=>r.dataset.sub===id&&(!key||!r.dataset.par||r.dataset.par===key));if(!sub)return false;
    fil.querySelectorAll('.agrow.on').forEach(r=>r.classList.remove('on'));sub.classList.add('on');
    const subs=sub.closest('.agrow-subs');if(subs){subs.classList.add('open');const pr=subs.previousElementSibling;if(pr)pr.classList.add('subs-open');}
    agSync(fil);updateAgBadges(fil);updateSubCounts(fil);return true;}
  /* v9p9: header selector toggle (From / To / Filter) + identity-badge summary in the trigger.
     Next-up item 8: the feed From/To filter, Prompt To, and the From selectors are IN-FLOW ACCORDION drawers
     (.dd--acc + .src-acc) — a STICKY toggle (no outside-click dismiss; Esc closes via closeSrcAccordions),
     the drawer pushing the content below down instead of overlaying it. Non-acc .src-dd instances (the
     Link-pair + reviewer pickers) keep the anchored-popover behavior. */
  function toggleSrcPop(btn){const dd=btn.closest('.src-dd');if(!dd)return;const pop=dd.querySelector('.src-pop');
    if(dd.classList.contains('dd--acc')){const open=pop.classList.toggle('open');dd.classList.toggle('open',open);return;}
    const open=pop.classList.contains('open');closeAllPopups();if(!open)pop.classList.add('open');}
  /* Next-up item 8: close every open accordion-selector drawer (the Escape path; outside clicks leave them open) */
  function closeSrcAccordions(){document.querySelectorAll('.src-dd.dd--acc.open').forEach(dd=>{dd.classList.remove('open');const p=dd.querySelector('.src-pop');if(p)p.classList.remove('open');});}
  function updateAgBadges(scope){const wrap=scope.querySelector('[data-badges]');if(!wrap)return;
    const on=[...scope.querySelectorAll('.aglist .agrow.on')].filter(r=>{
      if(r.classList.contains('agrow--sub')){const subs=r.closest('.agrow-subs');const par=subs&&subs.previousElementSibling;if(par&&par.classList.contains('on'))return false;}   /* a fully-selected parent's badge stands in for its subagents */
      return true;});
    const cap=scope.dataset.badgeCap?parseInt(scope.dataset.badgeCap,10):3;
    let html=on.slice(0,cap).map(r=>{
      if(r.classList.contains('agrow--sub')){const id=r.dataset.sub||'';const st=[...r.classList].find(c=>c.indexOf('sb-')===0)||'sb-idle';   /* subagent leaf → compact badge, parent identity in the name */
        const subs=r.closest('.agrow-subs');const par=subs&&subs.previousElementSibling;const pn=par?((par.querySelector('.ag-name')||{}).textContent||''):'';
        return '<span data-comp="identity-badge" class="badge badge-c badge-sub"><span class="sbadge '+st+' sub-fbadge">'+id+'</span><span class="b-lab"><span class="b-role">subagent</span><span class="b-name">'+pn+' › '+id+'</span></span></span>';}
      const tileEl=r.querySelector('.agtile');if(!tileEl)return '';const tile=tileEl.outerHTML;const role=(r.querySelector('.ag-role')||{}).textContent||'';const name=(r.querySelector('.ag-name')||{}).textContent||'';
      return '<span data-comp="identity-badge" class="badge badge-c">'+tile+'<span class="b-lab"><span class="b-role">'+role+'</span><span class="b-name">'+name+'</span></span></span>';}).join('');
    if(on.length>cap)html+='<span data-comp="overflow-badge" class="badge-more">+'+(on.length-cap)+'</span>';
    if(!on.length)html='<span class="b-empty">No agents</span>';
    wrap.innerHTML=html;LU();}
  /* Next-up item 7: a parent row's .ag-subcount reads SELECTED/TOTAL (e.g. "2/4"), recomputed live as leaf
     selections change (row toggles, All/None, the subagent-badge feed scoping). Same badge geometry. */
  function updateSubCounts(scope){if(!scope)return;scope.querySelectorAll('.agrow--parent').forEach(p=>{
    const b=p.querySelector('.ag-subcount');const subs=p.nextElementSibling;
    if(!b||!subs||!subs.classList.contains('agrow-subs'))return;
    const tot=subs.querySelectorAll('.agrow--sub').length,sel=subs.querySelectorAll('.agrow--sub.on').length;
    b.textContent=sel+'/'+tot;b.title=sel+' of '+tot+' subagent'+(tot===1?'':'s')+' selected';});}
  function pickAgRow(el){const w=el.closest('.aglist')||el.parentElement;w.querySelectorAll('.agrow').forEach(c=>c.classList.remove('on'));el.classList.add('on');} /* single-select (Source) */
  function agAllNone(btn){const s=btn.closest('[data-agscope]');if(!s)return;const on=btn.dataset.act!=='none';s.querySelectorAll('.agrow').forEach(r=>r.classList.toggle('on',on));agSync(s);updateAgBadges(s);updateSubCounts(s);if(s.id==='hist-from'&&typeof applyHistFilters==='function')applyHistFilters();}  /* contextual All / None toggle (+ item 7 recount, item 9 History-From filter) */
  function segPick(b){const g=b.closest('.seg');g.querySelectorAll('button').forEach(x=>x.classList.remove('active'));b.classList.add('active');}
  function pickOpt(el){const p=el.parentElement;p.querySelectorAll('.opt').forEach(o=>o.classList.remove('on'));el.classList.add('on');}
  function pickDecision(el){const c=el.closest('.fcard,.rcard');c.querySelectorAll('.opt').forEach(o=>o.classList.remove('on'));el.classList.add('on');const ap=c.querySelector('.dec-approve');if(ap)ap.disabled=false;}
  function miniToggle(el){el.classList.toggle('on');applyTxFilters();}
  function toggleSplitMenu(btn){const m=btn.parentElement.querySelector('.split-menu');const open=m.classList.contains('open');closeAllPopups();if(!open)m.classList.add('open');}
  function pickSplit(mi){const menu=mi.closest('.split-menu');menu.querySelectorAll('.split-mi').forEach(x=>x.classList.toggle('sel',x===mi));const l=menu.closest('.split').querySelector('.split-lbl');if(l){const base=mi.dataset.short||mi.querySelector('b').textContent;l.textContent=(l.dataset.prefix||'')+base;}menu.classList.remove('open');}
  function clearField(id){const el=document.getElementById(id);if(el){el.value='';if(el.classList.contains('autosize'))autosize(el);el.focus();}}
  function copyField(id){const el=document.getElementById(id);if(el&&navigator.clipboard)navigator.clipboard.writeText(el.value||el.textContent||'').catch(()=>{});}
  function copyCard(b){const c=b.closest('.rcard');const x=c?c.querySelector('.rc-body,.rc-log'):null;if(x&&navigator.clipboard)navigator.clipboard.writeText(x.textContent||'').catch(()=>{});}
  function replyTo(name){switchTab('prompt','compose');const w=document.getElementById('prompt-targets');if(w){const cs=[...w.querySelectorAll('.agrow')];cs.forEach(c=>c.classList.remove('on'));const m=cs.find(c=>{const n=c.querySelector('.ag-name');return n&&n.textContent.trim()===name;});if(m){m.classList.add('on');m.scrollIntoView({block:'nearest'});}agSync(w);updateAgBadges(w);}const pc=document.getElementById('pPrompts');if(pc){pc.classList.add('reply-flash');setTimeout(()=>pc.classList.remove('reply-flash'),900);}const f=document.getElementById('compose-field');if(f)f.focus();}
  /* Next-up items 3+18: the cycler defaults to A↔B (both) — the default lives in the markup (data-dir="both") — and the
     glyphs are Lucide arrows (arrow-right / arrow-left / arrow-left-right), swapped via innerHTML + LU() because Lucide
     replaces the <i> placeholder node, so textContent can't carry the icon. */
  function cycleDir(b){const o=['ab','ba','both'],g={ab:'arrow-right',ba:'arrow-left',both:'arrow-left-right'},t={ab:'A → B',ba:'B → A',both:'A ↔ B (both)'};let i=(o.indexOf(b.dataset.dir)+1)%3;b.dataset.dir=o[i];b.innerHTML='<i data-lucide="'+g[o[i]]+'"></i>';b.title=t[o[i]];LU();}
  function toggleLimit(b){b.classList.toggle('on');const i=b.parentElement.querySelector('.lim-in');if(i)i.disabled=!b.classList.contains('on');}
  /* 2026-07-17: toggleEdit (the Details-tab pencil edit-lock) is RETIRED — the whole Details tab is view-only
     (identity + config lock at create — ARCHITECTURE §7.15), so no pencil remains to serve. The .lockable grey
     is the permanent locked state (.field:not(.editing) .lockable in styles.css). */
  function step(b,d){const i=b.parentElement.querySelector('input');if(!i)return;let v=parseInt(i.value||'0',10)+d;const mn=i.min!==''?parseInt(i.min,10):0;if(!isNaN(mn))v=Math.max(mn,v);const mx=i.max!==''?parseInt(i.max,10):null;if(mx!==null&&!isNaN(mx))v=Math.min(mx,v);i.value=v;}
  function autosize(el){el.style.height='auto';const cs=getComputedStyle(el);const b=(parseFloat(cs.borderTopWidth)||0)+(parseFloat(cs.borderBottomWidth)||0);el.style.height=(el.scrollHeight+b)+'px';}
  function autosizeAll(){document.querySelectorAll('textarea.autosize').forEach(autosize);}
  function selectLibRow(el){el.parentElement.querySelectorAll('.lib-row').forEach(r=>r.classList.remove('on'));el.classList.add('on');}

  /* ===== v9p7 (A3) / L1 (ND 1+2): Library — Plan/Doc expand/collapse + two-column nav↔card sync + tab routing ===== */
  /* ND 2c: the entry list is a TRUE SINGLE-OPEN accordion (mirroring the Assets assetSel model) — opening any
     card closes its siblings and clears their nav highlight, so exactly one nav row reads open at a time. */
  function closeSiblingEntries(card){const list=card.parentElement;if(!list)return;
    [...list.querySelectorAll('.plan-card.open')].forEach(c=>{if(c!==card){c.classList.remove('open');syncNavHighlight(c.id);}});}
  function togglePlan(head){const c=head.closest('.plan-card');if(c){if(!c.classList.contains('open'))closeSiblingEntries(c);c.classList.toggle('open');syncNavHighlight(c.id);}LU();}   /* L1: opening/closing a card highlights/unhighlights its entry-nav row */
  function navRowFor(id){return document.querySelector('.docnav-row[data-navid="'+id+'"]');}
  /* L1: card→nav half of the bidirectional sync — a card's open state drives its nav row's .on */
  function syncNavHighlight(id){const card=document.getElementById(id);const row=navRowFor(id);if(row)row.classList.toggle('on',!!(card&&card.classList.contains('open')));}
  /* L1: generalized open+scroll+flash for BOTH Plans and Documents — picks the tab by id prefix (doc-* → Documents,
     else Plans), opens/scrolls/flashes the matching card, and highlights its nav row. reviewPlan is a thin call into
     this (the Inbox "Plans & Docs" Review action routes through it — same doc-/plan- id-prefix convention). */
  function openEntry(id){switchTab('doc',id.indexOf('doc-')===0?'documents':'plan');const card=document.getElementById(id);if(!card)return;
    closeSiblingEntries(card);   /* ND 2c: single-open accordion */
    card.classList.add('open');card.scrollIntoView({block:'nearest',behavior:'smooth'});
    card.classList.remove('plan-flash');void card.offsetWidth;card.classList.add('plan-flash');
    setTimeout(()=>card.classList.remove('plan-flash'),1000);syncNavHighlight(id);LU();}
  /* Inbox (Plan card) → review the full plan/doc in the Library, expanded + flagged */
  function reviewPlan(planId){openEntry(planId);}
  /* L1: nav→card half of the sync — an entry-nav row click opens/scrolls/flashes its card */
  function navPick(row){openEntry(row.dataset.navid);}
  /* L1: which lens (Outline/Feedback/Authors) a card's nav rail currently shows — so an edit-save repaint keeps it */
  function currentLensMode(id){const nav=document.querySelector('[data-plannav="'+id+'"]');if(!nav)return 'outline';
    if(nav.querySelector('.nav-tab--fb.on'))return 'feedback';if(nav.querySelector('.nav-tab--au.on'))return 'authors';return 'outline';}
  /* L1 (ND-3) → L3 (5d): per-card raw-markdown edit toggle for BOTH plan and doc cards — the Editor-header Edit ghost
     flips the rendered .doc-ed view ⇄ a raw textarea seeded from entry.md; Save writes back to entry.md and repaints
     the view in the card's current lens. entryById resolves plans and docs, so this is host-generic (plan cards now
     get the same working toggle docs use — planAct is reserved for approve/reject/revise). */
  function entryEdit(btn,id){const card=document.getElementById(id);if(!card)return;
    const ed=card.querySelector('.doc-ed');const ta=card.querySelector('.entry-edit');if(!ed||!ta)return;
    const e=entryById(id);const editing=ta.style.display!=='none';
    if(editing){if(e)e.md=ta.value;ta.style.display='none';
      const mode=currentLensMode(id);ed.outerHTML=mdEditorHTML(id,e?e.md:ta.value,mode);   /* fresh view (closed popout, no selection) — same repaint planNavMode uses */
      if(typeof clearSel==='function')clearSel(id);if(typeof refreshJumpPills==='function')refreshJumpPills();
      /* L3-panel fix: a raw-md save can change the checklist — refresh the promoted header steps chip in place
         (ND 14: it lives at the head of .plan-row.r2 now, in the old filename slot, outside the .doc-ed repaint),
         incl. appearing/disappearing at the 0 boundary. */
      if(e){const r2=card.querySelector('.plan-row.r2');
        if(r2){const dn=e.md.split('\n').filter(l=>/^\s*-\s*\[(x|X)\]/.test(l)).length;
          const sn=e.md.split('\n').filter(l=>/^\s*-\s*\[( |x|X)\]/.test(l)).length;
          let chip=r2.querySelector('.cnt-chip.c-steps');
          if(!sn){if(chip)chip.remove();}
          else{if(!chip){r2.insertAdjacentHTML('afterbegin','<span data-comp="count-chip" class="cnt-chip c-steps"><i data-lucide="list-checks"></i><span class="cn"></span></span>');chip=r2.querySelector('.cnt-chip.c-steps');}
            if(chip){chip.classList.toggle('all',dn===sn);chip.title=dn+' of '+sn+' steps done';const cn=chip.querySelector('.cn');if(cn)cn.textContent=dn+'/'+sn+' steps';}}}}
      btn.innerHTML='<i data-lucide="square-pen"></i>';btn.title='Edit';}
    else{ta.value=e?e.md:ta.value;ed.style.display='none';ta.style.display='block';
      btn.innerHTML='<i data-lucide="check"></i>';btn.title='Save';ta.focus();}
    if(typeof syncEditorMics==='function')syncEditorMics();LU();}
  function docAdd(){toast('Add a document — choose a file to add to the Library');}
  /* (ND 14: planCopy is retired with the Editor-header Copy ghost — the merged Export control's "Copy selected"
     covers copying; the header runs Comment → Edit → Mic now.) */
  /* plan decision/edit/copy (scripted demo): mutate PLANS state + re-render so the card, badges + count update */
  function reopenPlan(id){const c=document.getElementById(id);if(c){closeSiblingEntries(c);c.classList.add('open');c.scrollIntoView({block:'nearest'});syncNavHighlight(id);}LU();}   /* ND 2c: keeps the single-open discipline on programmatic reopens */
  /* decision/edit/copy for BOTH plans and docs (scripted demo): mutate the entry + re-render the right surface so the
     card, badges + tab count update. L1 (ND-6): docs now share the full decision trio (Revise · Reject · Approve). */
  function planAct(a,id){const p=entryById(id)||PLANS.find(x=>x.open)||DOCS.find(x=>x.open);if(!p)return;const own=AG[p.owner]?AG[p.owner].name:p.owner;
    const isDoc=p.id.indexOf('doc-')===0;const rerender=isDoc?renderDocs:renderPlans;const kind=isDoc?'Doc':'Plan';
    if(a==='edit'){toast('Editing '+p.file+' — line-numbered editor');return;}
    if(a==='revise'){toast('Flagged sections sent back to '+own+' to revise');return;}
    if(a==='reject'){p.status='draft';toast(kind+' rejected — returned to draft');rerender();reopenPlan(p.id);return;}
    if(a==='approve'){p.status='approved';toast(kind+' approved — '+own+' may proceed');rerender();reopenPlan(p.id);
      if(typeof pushApprovalToInbox==='function')pushApprovalToInbox(p);return;}}

  /* L3: the retired v1.2 doc-switcher (docPick + the one-at-a-time .docdoc panes) is fully removed — the Documents
     tab is the two-column entry-nav (renderEntryNav) + plan-style cards now; its last dead caller left with the
     doc-switcher card of the gallery (the catalog was retired 2026-07-05 → archive/design/). */

  /* ===== v10p1 #18-21: Assets as a rail + preview (like Documents) + the shared Documents/Assets
     header & footer + Add menu + nav-row rename/delete. Assets is the single source of truth for media. ===== */
  const ASSETS=[
    {id:'mockup-v9',name:'mockup-v9.png',path:'design/mockup-v9.png',meta:'PNG · 1840×1120 · 412 KB',created:'Jun 18 · 6d ago',edited:'Jun 20 · 18h ago',grad:'linear-gradient(135deg,var(--main),var(--secondary))'},
    {id:'palette-ref',name:'palette-ref.png',path:'design/palette-ref.png',meta:'PNG · 1200×800 · 188 KB',created:'Jun 12 · 12d ago',edited:'Jun 12 · 12d ago',grad:'linear-gradient(135deg,var(--ag-violet),var(--ag-azure))'},
    {id:'graph-sketch',name:'graph-sketch.jpg',path:'design/graph-sketch.jpg',meta:'JPG · 1024×768 · 96 KB',created:'Jun 10 · 14d ago',edited:'Jun 10 · 14d ago',grad:'linear-gradient(135deg,var(--ag-amber),var(--ag-gold))'},
    {id:'inbox-flow',name:'inbox-flow.png',path:'design/inbox-flow.png',meta:'PNG · 1600×900 · 274 KB',created:'Jun 19 · 5d ago',edited:'Jun 19 · 5d ago',grad:'linear-gradient(135deg,var(--ag-emerald),var(--ag-cyan))'},
    {id:'flow-spec',name:'flow-spec.pdf',path:'design/flow-spec.pdf',meta:'PDF · 6 pages · 1.1 MB',created:'Jun 21 · 3d ago',edited:'Jun 21 · 3d ago'}   /* ND 10: a non-image asset so the fixed slot's file-type-icon form renders */
  ];
  let assetSel='mockup-v9';
  /* A18: nav rows keep ONLY the Rename (pencil) ghost icon — the Delete (trash) ghost icon is removed (remove still
     available from the card footer). Rename works on images too, so it stays un-greyed. */
  function navActsHTML(){return '<span class="docnav-acts"><button data-comp="ghost-icon-button" class="ghost-ic" title="Rename" onclick="navRename(event,this)"><i data-lucide="pencil"></i></button></span>';}
  /* A18: per-type file icon (lucide) by extension — doc vs image — replacing the doc-icon / gradient thumbnail */
  function fileTypeIcon(name){const ext=(name.split('.').pop()||'').toLowerCase();
    if(['png','jpg','jpeg','gif','webp','svg','bmp','tiff'].includes(ext))return 'file-image';
    return 'file-text';}
  function isImageFile(name){const ext=(name.split('.').pop()||'').toLowerCase();return ['png','jpg','jpeg','gif','webp','svg','bmp','tiff'].includes(ext);}
  /* ND 10: the Assets leading slot is a FIXED FOOTPRINT — image files show a full-height THUMBNAIL (the seeded
     gradient stands in for the real thumb; in the app it's Electron nativeImage.createThumbnailFromPath via the
     Windows Shell provider, app.getFileIcon() the fallback — docs/ARCHITECTURE.md §7.16), non-image / unsupported
     files a same-size file-type ICON. This reverses the earlier icon-only "A18" call for images. */
  function assetThumbHTML(a){return isImageFile(a.name)
    ?'<span data-comp="asset-thumb" data-variants="icon" class="asset-thumb" style="background:'+(a.grad||'var(--surface-3)')+'" title="'+esc(a.name)+'"></span>'
    :'<span data-comp="asset-thumb" class="asset-thumb asset-thumb--icon" title="'+esc(a.name)+'"><i data-lucide="'+fileTypeIcon(a.name)+'"></i></span>';}
  function addMenuHTML(group){return '<div data-comp="add-menu" class="docnav-addwrap"><button class="docnav-add" onclick="toggleAddMenu(event,this)"><i data-lucide="plus"></i>Add '+(group==='assets'?'asset':'document')+'</button>'
    +'<div class="add-menu"><button class="add-mi" onclick="addDoc(event,\''+group+'\',\'file\')"><b><i data-lucide="folder-open"></i>Add file</b><span class="add-sub">Open the explorer</span></button>'
    +'<button class="add-mi" onclick="addDoc(event,\''+group+'\',\'paste\')"><b><i data-lucide="clipboard"></i>Paste</b><span class="add-sub">From the clipboard, auto-named</span></button></div></div>';}
  function renderAssets(){const nav=document.getElementById('asset-nav'),main=document.getElementById('asset-main');if(!nav||!main)return;
    if(ASSETS.length&&!ASSETS.find(a=>a.id===assetSel))assetSel=ASSETS[0].id;
    nav.innerHTML=ASSETS.map(a=>'<div class="docnav-row assetnav-row'+(a.id===assetSel?' on':'')+'" role="button" tabindex="0" data-asset="'+a.id+'" onclick="assetPick(this)">'
      +assetThumbHTML(a)   /* ND 10: fixed-footprint leading slot — thumbnail for images, same-size file-type icon otherwise */
      +'<span class="docnav-lab"><span class="docnav-name">'+esc(a.name)+'</span><span class="docnav-path">'+esc(a.meta.split(' · ').pop())+'</span></span>'
      +navActsHTML()+'</div>').join('')+addMenuHTML('assets');
    main.innerHTML=ASSETS.map(a=>'<div data-comp="asset-card" class="assetdoc'+(a.id===assetSel?' on':'')+'" data-asset="'+a.id+'">'
      +'<div class="doc-header"><span class="dh-path">'+esc(a.path)+'</span><span class="dh-dates"><b>Created</b> '+a.created+'&nbsp;&nbsp;<b>Edited</b> '+a.edited+'</span></div>'
      +'<div class="asset-preview"><span class="ap-img" style="background:'+(a.grad||'var(--surface-3)')+'"'+(a.grad?'':' data-noimg')+'><i data-lucide="'+(isImageFile(a.name)?'image':fileTypeIcon(a.name))+'"'+(a.grad?'':' style="color:var(--muted)"')+'></i></span></div>'
      +'<div class="doc-foot" data-libfoot="asset-'+a.id+'" data-libkind="asset"></div></div>').join('');
    main.querySelectorAll('[data-libfoot]').forEach(s=>{s.innerHTML=libFootHTML(s.dataset.libfoot,s.dataset.libkind);});
    LU();}
  function assetPick(row){const id=row.dataset.asset;assetSel=id;
    const nav=document.getElementById('asset-nav'),main=document.getElementById('asset-main');
    if(nav)nav.querySelectorAll('.assetnav-row').forEach(r=>r.classList.toggle('on',r===row));
    if(main)main.querySelectorAll('.assetdoc').forEach(d=>d.classList.toggle('on',d.dataset.asset===id));LU();}
  /* P3 (#119) → ND 14: the Library "Editor" header for Plans + Documents — the entry's FILENAME rides inline
     after the "Editor" label (moved off the card header's row 2), the Copy ghost is removed, and the icons run
     Comment → Edit → Mic with the mic right-aligned. Assets gets no header (an image isn't text-editable). */
  function editHeadHTML(editClick,cmtHost,editCls,micField,fname){return '<div data-comp="editor-header" data-variants="rec" class="lib-edit-head"><span class="lib-edit-lab">Editor</span>'
    +(fname?'<span class="lib-edit-fname" title="'+esc(fname)+'">'+esc(fname)+'</span>':'')
    +'<span class="flex-1"></span>'
    +'<button data-comp="ghost-icon-button" class="ghost-ic cmt-btn is-off" data-cmthost="'+cmtHost+'" data-verdict="approve" onclick="openComposerFromCtl(this)" title="Comment on the selected line / section"><i data-lucide="message-square-plus"></i></button>'
    +'<button data-comp="ghost-icon-button" class="ghost-ic '+(editCls||'')+'" onclick="'+editClick+'" title="Edit"><i data-lucide="square-pen"></i></button>'
    +'<button data-comp="ghost-icon-button" class="ghost-ic editor-mic" data-micfield="'+(micField||'')+'" title="Dictate (voice → text)" onclick="toggleMic(this)" onmousedown="event.preventDefault()" disabled><i data-lucide="mic"></i></button></div>';}
  /* L1: libFootHTML now serves ASSETS only — the Documents footer became the FULL planFootHTML (Export · Reviewer chip ·
     Revise·Reject·Approve, same as Plans). Assets keep the plain Export + Remove footer (an image is whole-file, so only
     Attach is enabled on it; no Review chip / Revise). The old doc-footer branch + its docRevise are retired. */
  function libFootHTML(host,kind){return expMenuHTML(host)+'<span class="flex-1"></span>'
      +'<button data-comp="icon-button" class="icon-btn icon-btn--danger" onclick="libRemove(\''+host+'\',\''+kind+'\')" title="Remove"><i data-lucide="trash-2"></i></button>';}
  function libCopy(host,kind){if(kind==='asset'){const a=ASSETS.find(x=>'asset-'+x.id===host);if(a){if(navigator.clipboard)navigator.clipboard.writeText(a.path).catch(()=>{});toast('Copied '+a.name+' path');}return;}copyField(host+'-edit');toast('Copied');}
  function libRemove(host,kind){if(kind==='asset'){const id=host.replace('asset-','');const i=ASSETS.findIndex(x=>x.id===id);if(i<0)return;const nm=ASSETS[i].name;ASSETS.splice(i,1);if(assetSel===id)assetSel=ASSETS.length?ASSETS[0].id:'';renderAssets();toast('Removed '+nm);return;}
    const i=DOCS.findIndex(d=>d.id===host);if(i<0)return;const nm=DOCS[i].file;DOCS.splice(i,1);renderDocs();toast('Removed '+nm);}   /* L1: docs live in DOCS now (the Remove button itself is dropped from the doc footer; this stays for nav-delete/programmatic use) */
  /* Add menu (#20) + nav-row rename/delete (#21), shared by Documents + Assets */
  function toggleAddMenu(e,btn){e.stopPropagation();const w=btn.closest('.docnav-addwrap');const m=w.querySelector('.add-menu');const open=m.classList.contains('open');
    document.querySelectorAll('.add-menu.open').forEach(x=>x.classList.remove('open'));if(!open)m.classList.add('open');}
  function addDoc(e,group,how){if(e)e.stopPropagation();document.querySelectorAll('.add-menu.open').forEach(x=>x.classList.remove('open'));
    if(how==='file'){toast((group==='assets'?'Add asset':'Add document')+' — choose a file in the explorer');return;}
    if(group==='assets'){const n=ASSETS.filter(a=>/^pasted-/.test(a.id)).length+1;const id='pasted-'+n;
      ASSETS.push({id:id,name:'pasted-'+n+'.png',path:'.scratch/pasted-'+n+'.png',meta:'PNG · clipboard · 64 KB',created:'now',edited:'now',grad:'linear-gradient(135deg,var(--ag-teal),var(--ag-citron))'});
      assetSel=id;renderAssets();toast('Pasted image → pasted-'+n+'.png');}
    else addDocPaste('',null);}   /* R-batch item 9: paste → a new Documents row with an editable dummy name, opened with inline rename active */
  /* R-batch items 8/9: SILENT doc creation — builds a new Documents row + editor pane (the same wiring renderDocs()
     uses) from content + a name, WITHOUT switching tabs or opening rename. Returns {key,name,path}. Used by both
     addDocPaste (Export → file / Add-menu Paste, which then lands you in Documents) and the merged control's
     "Attach as file" (item 8, which saves the doc then reveals a chip in Compose). */
  let docPasteSeq=0;
  function createDoc(content,suggestedName){
    const name=suggestedName||('untitled-'+(docPasteSeq+1)+'.md');const key='doc-pasted-'+(++docPasteSeq);const path='.scratch/'+name;   /* L1: docs are DOCS entries now — push a plan-shaped seed + re-render (no per-doc .docdoc pane) */
    DOCS.push({id:key,file:name,path:path,status:'draft',title:name,owner:'user',open:false,created:'now',createdAgo:'now',edited:'now',editedAgo:'now',md:content||'',feedback:[],authors:[]});
    renderDocs();
    return {key:key,name:name,path:path};
  }
  /* Export → file / Add-menu Paste: create the doc, then SWITCH to Documents, open its card, and open inline RENAME. */
  function addDocPaste(content,suggestedName){
    const d=createDoc(content,suggestedName);if(!d.key)return;
    switchTab('doc','documents');
    const pane=document.getElementById('doc-documents');const row=pane&&pane.querySelector('.docnav-row[data-navid="'+d.key+'"]');
    if(row){navPick(row);const pencil=row.querySelector('.docnav-acts .ghost-ic');if(pencil)navRename({stopPropagation(){}},pencil);}
    LU();
  }
  function navRename(e,btn){e.stopPropagation();const row=btn.closest('.docnav-row');const lab=row.querySelector('.docnav-name');if(!lab||row.querySelector('.docnav-name-edit'))return;
    const cur=lab.textContent;const inp=document.createElement('input');inp.className='docnav-name-edit';inp.value=cur;
    lab.style.display='none';lab.parentElement.insertBefore(inp,lab);inp.focus();inp.select();inp.onclick=ev=>ev.stopPropagation();
    const commit=()=>{const v=(inp.value.trim()||cur);lab.textContent=v;lab.style.display='';inp.remove();
      if(row.dataset.asset){const a=ASSETS.find(x=>x.id===row.dataset.asset);if(a)a.name=v;}
      else if(row.dataset.navid){const en=entryById(row.dataset.navid);if(en){const fn=en.path.split('/').pop();en.path=en.path.slice(0,en.path.length-fn.length)+v;en.file=v;renderDocs();}}   /* L1: a doc rename updates the DOCS entry (path filename + card label) then re-renders */
      toast('Renamed → '+v);};
    inp.onkeydown=ev=>{if(ev.key==='Enter'){ev.preventDefault();inp.blur();}else if(ev.key==='Escape'){inp.value=cur;inp.blur();}};inp.onblur=commit;}
  function navDelete(e,btn){e.stopPropagation();const row=btn.closest('.docnav-row');if(!row)return;
    if(row.classList.contains('assetnav-row'))libRemove('asset-'+row.dataset.asset,'asset');else libRemove(row.dataset.navid,'doc');}   /* L1: doc rows carry data-navid = the DOCS entry id */

  function closeAllPopups(){document.querySelectorAll('.split-menu.open,.fmt-menu.open,.picker-pop.open,.combo-pop.open,.msel-pop.open,.src-pop.open:not(.src-acc),.vpop.open,.att-pop.open,.add-menu.open,.exp.open').forEach(x=>x.classList.remove('open'));document.querySelectorAll('.fcard.att-open').forEach(c=>c.classList.remove('att-open'));document.querySelectorAll('.plan-card.pop-open').forEach(c=>c.classList.remove('pop-open'));}   /* R-batch item 3: the subagent accordion (.subs-acc.open) is a STICKY toggle, not a popup — intentionally NOT closed here. R11 item 5: also drop the .plan-card overflow-release toggled by footer popovers. Next-up item 8: the accordion-selector drawers (.src-pop.src-acc) are sticky toggles too — excluded here, closed only by their trigger or Escape (closeSrcAccordions). */
  /* R-batch item 2: the subagent +N overflow badge opens a popover listing the hidden subs (preserves the
     card's fixed square height — no in-place expansion). Click is already isolated from the card select. */
  /* R-batch item 3: subagent accordion drawer. has-more is set when the badges wrap past one row (recomputed on
     load + resize, since wrap depends on the card's width). Clicking the strip toggles the drawer open and grows
     the card (.node.subs-open); state sticks. A badge's own stopPropagation keeps a badge click isolated from both
     the drawer and card-select. scrollHeight reports the FULL content height (ignores the collapsed max-height clip),
     so it's a reliable wrap test whether the drawer is open or not. */
  function initSubsAcc(){document.querySelectorAll('.node-subs .subs-acc').forEach(acc=>{
    const b=acc.querySelector('.subs-badges');if(!b)return;
    const wraps=b.scrollHeight>20;   /* >1 badge row (16px + tolerance) */
    acc.classList.toggle('has-more',wraps);
    if(!wraps){acc.classList.remove('open');const n=acc.closest('.node');if(n)n.classList.remove('subs-open');}
  });}
  function subsTrig(e,el){const acc=el.closest('.subs-acc');if(!acc||!acc.classList.contains('has-more'))return;   /* one row → no drawer; let the click bubble up to select the node */
    e.stopPropagation();const open=acc.classList.toggle('open');const n=acc.closest('.node');if(n)n.classList.toggle('subs-open',open);LU();}

  /* ===== subagent model — group+member badges (A2), Details audit accordion, badge-click (resolves OQ-1) ===== */
  /* Details → "Subagents" audit accordion: a sticky disclosure (like the node drawer, NOT a popup → not closed by closeAllPopups). */
  function toggleSubsAudit(btn){const acc=btn.closest('.subs-audit');if(!acc)return;const open=acc.classList.toggle('open');btn.setAttribute('aria-expanded',open?'true':'false');if(typeof refreshJumpPills==='function')setTimeout(refreshJumpPills,30);}
  /* Open the audit accordion on Details and scroll + highlight the row for `subId` (e.g. "A2"). */
  function openSubsAudit(subId){
    if(typeof switchTab==='function')switchTab('mid','details');
    const acc=document.getElementById('det-subs-audit');if(!acc)return;
    acc.classList.add('open');const hd=acc.querySelector('.subs-audit-head');if(hd)hd.setAttribute('aria-expanded','true');
    acc.querySelectorAll('.sa-row.sa-hl').forEach(r=>r.classList.remove('sa-hl'));
    const row=subId?acc.querySelector('.sa-row[data-sub="'+subId+'"]'):null;
    if(row)row.classList.add('sa-hl');
    setTimeout(()=>{(row||acc).scrollIntoView({block:'center',behavior:'smooth'});},40);}
  /* Graph-card subagent badge click — replaces the old stopPropagation no-op (OQ-1). Three actions:
     (1) focus the PARENT agent, (2) open Details → Subagents scrolled+highlighted to that row,
     (3) scope the Feed to that subagent on the Messages tab. Still stops propagation so the
     click doesn't also select the card or toggle the badge drawer. */
  function subBadgeClick(e,badge){
    e.stopPropagation();
    const id=(badge.textContent||'').trim();
    const node=badge.closest('.node');
    if(node&&typeof selectNode==='function')selectNode(node);            /* (1) */
    openSubsAudit(id);                                                    /* (2) */
    if(typeof switchTab==='function')switchTab('feed','transcript');        /* (3) */
    if(typeof setFeedSubFilter==='function')setFeedSubFilter(node,id);
    const pn=node?(node.querySelector('.text-foreground.truncate')||{}).textContent||'':'';
    toast('Feed scoped → '+(pn?pn.replace(/^\d+\s+/,'').trim()+' › ':'')+id);}

  /* ===== Per-card inbox footer — a parallel view of each agent's open Inbox items =====
     Splits each graph card's footer: subagents on the LEFT (.subs-acc), a small envelope+count on the RIGHT
     (.node-inbox). The envelope is a FAITHFUL MIRROR of that agent's open Inbox items (REQS filtered by agent) — so
     resolving via either surface (the footer row deep-links to the Inbox card; the status badge is the fast path to
     the one blocking thing) clears the item from both. Count = OPEN items (not read); an item leaves only when
     completed. Two states: open items → teal envelope + count, expandable to a drawer of typed rows; none → dimmed,
     non-expandable. The drawer is INDEPENDENT of the subagents drawer (both can be open) and grows the card downward.
     Built once from REQS at boot (before initSubsAcc, so the badge-wrap measure accounts for the envelope's width). */
  function renderNodeInboxes(){
    document.querySelectorAll('.graph-grid .node').forEach(node=>{
      const subs=node.querySelector('.node-subs');if(!subs||subs.dataset.ninb)return;   /* build once per card */
      subs.dataset.ninb='1';
      const key=agKeyFromNode(node);
      const items=REQS.filter(r=>r.ag===key);
      const inner=subs.innerHTML;   /* preserve the existing subagents content (.subs-acc / .subs-empty) */
      let trig,drawer='';
      if(items.length){const n=items.length;
        trig='<button data-comp="node-inbox" class="node-inbox" onclick="ninbTrig(event,this)" aria-expanded="false" title="Inbox — '+n+' open item'+(n===1?'':'s')+' · click to expand"><i data-lucide="mail" class="ninb-ic"></i><span class="ninb-n">'+n+'</span></button>';
        drawer='<div class="ninb-drawer">'+items.map(o=>'<button class="ninb-row" onclick="ninbGoto(event,\''+key+'\',\''+o.type+'\')" title="Open in Inbox → '+secLabel(o.type)+'"><span class="ninb-type ninb-type--'+o.type+'">'+secLabel(o.type)+'</span><span class="ninb-row-t">'+esc(o.title)+'</span></button>').join('')+'</div>';
      } else {
        trig='<span data-comp="node-inbox" class="node-inbox node-inbox--empty" title="Inbox — no open items"><i data-lucide="mail" class="ninb-ic"></i></span>';
      }
      subs.innerHTML='<div class="node-subs-bar">'+inner+trig+'</div>'+drawer;
    });
  }
  /* toggle the per-card inbox drawer (independent of the subagents drawer); a dimmed/empty envelope doesn't expand */
  function ninbTrig(e,el){e.stopPropagation();if(el.classList.contains('node-inbox--empty'))return;
    const node=el.closest('.node');if(!node)return;
    const open=node.classList.toggle('ninb-open');el.setAttribute('aria-expanded',open?'true':'false');LU();}
  /* deep-link a footer row into the Feed → Inbox — scroll + expand + select + flash that agent's typed card.
     The parallel path to the status badge's statusJump; the item stays open until it's actually completed there. */
  function ninbGoto(e,key,type){e.stopPropagation();
    if(typeof switchTab==='function')switchTab('feed','inbox');
    const card=document.querySelector('#feed-inbox .inbox-card--'+type+'[data-agent="'+key+'"]');
    if(card){card.classList.add('open','sel');card.scrollIntoView({block:'nearest',behavior:'smooth'});
      card.classList.remove('reply-flash');void card.offsetWidth;card.classList.add('reply-flash');setTimeout(()=>card.classList.remove('reply-flash'),1000);
      if(typeof eaUpdate==='function')eaUpdate('feed');}
    LU();toast('Inbox → '+secLabel(type));}

  /* ===== Compose placeholders + merged Templates (v10p1 #22) ===== */
  let phSel=null;
  function setFillEnabled(on){const ta=document.getElementById('tpl-fill-input');const r=document.querySelector('#prompt-compose .fill-btn:not(.fill-btn--go)');const g=document.querySelector('#prompt-compose .fill-btn--go');
    [ta,r,g].forEach(e=>{if(e)e.disabled=!on;});if(!on&&ta){ta.value='';}}
  function pickPlaceholder(el){const f=document.getElementById('compose-field')||document;f.querySelectorAll('.ph-text').forEach(p=>p.classList.remove('sel'));el.classList.add('sel');phSel=el;
    const blk=el.closest('.ed-block--template');if(blk){f.querySelectorAll('.ed-block--template.sel').forEach(b=>b.classList.remove('sel'));blk.classList.add('sel');}   /* P3: a pill click also makes its template block the active one */
    setFillEnabled(true);const ta=document.getElementById('tpl-fill-input');if(!ta)return;ta.setAttribute('placeholder',el.dataset.tag||'');ta.value=el.dataset.value||'';autosize(ta);ta.focus();}
  function fillPlaceholder(){if(!phSel){toast('Tap a placeholder pill first');return;}const ta=document.getElementById('tpl-fill-input');const v=ta.value.trim();phSel.dataset.value=v;if(v){phSel.classList.add('filled');phSel.textContent=v;}else{phSel.classList.remove('filled');phSel.textContent=phSel.dataset.tag;}phSel.classList.add('sel');}
  function resetPlaceholder(){if(!phSel)return;phSel.dataset.value='';phSel.classList.remove('filled');phSel.textContent=phSel.dataset.tag;const ta=document.getElementById('tpl-fill-input');if(ta){ta.value='';autosize(ta);ta.focus();}}
  /* a placeholder pill — contenteditable=false so it stays an atomic, clickable token inside the box */
  function phSpan(tag,value){const filled=value!=null&&value!=='';
    return '<span data-comp="placeholder-pill" data-variants="filled" class="ph-text'+(filled?' filled':'')+'" data-tag="'+esc(tag)+'"'+(filled?' data-value="'+esc(value)+'"':'')+' contenteditable="false" onclick="pickPlaceholder(this)">'+esc(filled?value:tag)+'</span>';}
  const TEMPLATES=[
    {name:'Security audit request',body:()=>'Run a focused security audit of '+phSpan('{target_module}','src/auth/*')+'. Flag anything at or above '+phSpan('{severity_threshold}')+' severity, with a concrete exploit path for each finding. Post results to '+phSpan('{destination}','the shared scratchpad')+' grouped by severity, and notify '+phSpan('{notify_agent}')+' when the '+phSpan('{format}')+' summary is ready.'},
    {name:'Code review request',body:()=>'Review the diff on '+phSpan('{branch}','feature/*')+' for '+phSpan('{focus}','correctness & security')+'. Call out blocking issues first, then nits, and confirm the '+phSpan('{test_scope}')+' tests cover the change before approving.'},
    {name:'Refactor proposal',body:()=>'Propose a refactor of '+phSpan('{module}')+' to improve '+phSpan('{goal}','readability')+'. Keep behavior identical, lay the steps out as a checklist, and flag any risky '+phSpan('{risk_area}')+' touchpoints.'},
    {name:'Bug triage & severity',body:()=>'Triage '+phSpan('{issue}')+': reproduce it, assign a severity ('+phSpan('{severity}')+'), identify the root cause, and suggest an owner. Post the writeup to '+phSpan('{destination}','the scratchpad')+'.'}
  ];
  function buildTemplateOptions(){const sel=document.getElementById('tpl-select');if(!sel)return;
    sel.innerHTML='<option value="">None</option>'+TEMPLATES.map((t,i)=>'<option value="'+i+'">'+esc(t.name)+'</option>').join('');}
  let composeRange=null;
  function composeField(){return document.getElementById('compose-field');}
  function saveComposeRange(){const f=composeField();if(!f)return;const sel=window.getSelection();if(sel&&sel.rangeCount){const r=sel.getRangeAt(0);if(f.contains(r.commonAncestorContainer))composeRange=r.cloneRange();}}
  /* select a template → insert its body at the cursor (or append if the box isn't focused) without wiping
     existing text; None clears the active template + re-greys the fill input. The box stays fully editable. */
  /* P3 (#118): picking a template inserts a selectable template BLOCK (the P1a primitive) at the cursor —
     not inline raw text. The active block (.sel) is the one the fill input drives; None deselects + greys. */
  function applyTemplate(idx){const f=composeField();if(!f)return;
    if(idx===''){phSel=null;setFillEnabled(false);f.querySelectorAll('.ed-block--template.sel,.ph-text.sel').forEach(p=>p.classList.remove('sel'));return;}
    const t=TEMPLATES[parseInt(idx,10)];if(!t)return;
    f.querySelectorAll('.ed-block--template.sel').forEach(b=>b.classList.remove('sel'));
    const html=blockHTML('template',{source:'Template · '+t.name,body:t.body(),active:true,tpl:idx,kindLabel:'template'});
    const frag=document.createRange().createContextualFragment(html);
    if(composeRange&&f.contains(composeRange.commonAncestorContainer)){composeRange.collapse(false);composeRange.insertNode(frag);}
    else f.appendChild(frag);
    setFillEnabled(true);LU();}
  /* P3: when a template block becomes active, enable the fill input + sync the picker to it */
  function onTplBlockSelected(el){setFillEnabled(true);const sel=document.getElementById('tpl-select');if(sel&&el.dataset.tpl!=null&&el.dataset.tpl!=='')sel.value=el.dataset.tpl;}
  function copyCompose(){const f=composeField();if(f&&navigator.clipboard)navigator.clipboard.writeText(f.innerText||f.textContent||'').catch(()=>{});toast('Editor copied');}
  function clearCompose(){const f=composeField();if(f){f.innerHTML='';composeRange=null;f.focus();}}

  /* ============================ P3 (#109) — the attachment-chip strip (above the Editor) ============================ */
  /* Horizontal chips styled like the Library nav cards — each removable (×) and click-to-open in the Library.
     Seeded with representative items; P4's Attach pushes here (a real path for files, a temp-style path for
     materialized content). Hidden when empty. */
  const ATTACH=[
    {id:'a1',name:'auth-token-rotation.md',path:'~/.claude/plans/auth-token-rotation-shimmering-falcon.md',type:'doc'},
    {id:'a2',name:'jwt-expiry-trace.png',path:'assets/jwt-expiry-trace.png',type:'asset'}
  ];
  function attIcon(t){return t==='asset'?'image':(t==='temp'?'file-clock':'file-text');}
  function renderAttachStrip(){const el=document.getElementById('attach-strip');if(!el)return;
    const sec=document.getElementById('attach-section');   /* #16: toggle the heading+strip section together so the "Attachments" label hides when empty */
    if(!ATTACH.length){if(sec)sec.style.display='none';el.innerHTML='';return;}
    if(sec)sec.style.display='';
    el.innerHTML=ATTACH.map((at,i)=>
      '<span data-comp="attachment-chip" data-variants="flash" class="att-card" data-ai="'+i+'" data-att="'+esc(at.id)+'" title="'+esc(at.path)+'"><i data-lucide="'+attIcon(at.type)+'" class="att-card-ic"></i>'
        +'<span class="att-card-nm" onclick="openAttachmentCard(event,'+i+')">'+esc(at.name)+'</span>'
        +'<button class="att-card-cite" type="button" onclick="citeAttachment(event,'+i+')" title="Cite this attachment in the prose"><i data-lucide="link"></i></button>'   /* P4b: insert an inline citation pill at the cursor */
        +'<button class="att-card-x" type="button" onclick="removeAttachment(event,'+i+')" title="Remove attachment"><i data-lucide="x"></i></button></span>').join('');
    LU();}
  function openAttachmentCard(e,i){if(e)e.stopPropagation();const at=ATTACH[i];if(!at)return;
    if(at.type==='temp'){toast('Materialized temp file — '+at.path);return;}
    switchTab('doc',at.type==='asset'?'assets':'documents');toast('Opening '+at.name+' in the Library');}
  function removeAttachment(e,i){if(e)e.stopPropagation();const at=ATTACH[i];if(!at)return;ATTACH.splice(i,1);
    onAttachmentRemoved(at);   /* P4b: deleting an attachment cascades to remove its citations */
    renderAttachStrip();}
  function addAttachment(at){ATTACH.push(at);renderAttachStrip();}   /* P4a Attach hook */

  /* ============================ P4a — the Embed/Attach control ============================ */
  /* Replaces Share + Link-to-prompt on the Library footers + the Feed action strip. A section/line/block
     selection → Embed (drop a frozen embed block into the Editor); a whole-doc/title selection or an Asset
     (or whole feed card[s]) → Attach (add a chip: a real path for files, a temp-style path for materialized
     content). The link icon sends in whichever mode the selection enables; the other mode greys. */
  let attSeq=100;
  function nextAttId(){return 'att-'+(++attSeq);}
  /* R-batch items 6-10: ONE merged Export control (replaces the separate Output-Export .exp + Embed/Attach .ea-dd).
     Two sections — "Export" (Copy selected · Export selected → file) and "Add to prompt" (Embed in prompt · Attach as
     file) — Cut is gone. Reused across feed / hist / doc-* / plan / asset hosts (data-eahost). Selection-gating
     (eaUpdate) enables each item per the current selection. Kept the .ea-dd class + eaSend wiring so every existing
     selection-change caller keeps working; data-eamode now carries the four actions. */
  function expMenuHTML(host){return '<div data-comp="export-control" class="exp ea-dd" data-eahost="'+esc(host)+'"><button class="exp-btn" title="Export · add to prompt…" onclick="event.stopPropagation();toggleExport(this)"><i data-lucide="download" class="ic"></i><i data-lucide="chevron-down" class="cv"></i></button>'
    +'<div class="exp-menu">'
    +'<div class="exp-h">Copy &amp; Export</div>'
    +'<button class="exp-mi ea-mi" data-eamode="copy" onclick="eaSend(this)" disabled><i data-lucide="copy"></i><span class="lead"><b>Copy selected</b><span class="sub">the selection to the clipboard</span></span></button>'
    +'<button class="exp-mi ea-mi" data-eamode="file" onclick="eaSend(this)" disabled><i data-lucide="file-down"></i><span class="lead"><b>Export selected → file</b><span class="sub">new doc in Library → Documents</span></span></button>'
    +'<div class="exp-h">Add to prompt</div>'
    +'<button class="exp-mi ea-mi" data-eamode="embed" onclick="eaSend(this)" disabled><i data-lucide="quote"></i><span class="lead"><b>Embed in prompt</b><span class="sub">drop a frozen quoted block into the Editor</span></span></button>'
    +'<button class="exp-mi ea-mi" data-eamode="attach" onclick="eaSend(this)" disabled><i data-lucide="paperclip"></i><span class="lead"><b>Attach as file</b><span class="sub">save it as a doc + add a path chip to the Editor</span></span></button>'
    +'</div></div>';}
  function eaSelKind(host){
    if(host==='feed'){if(document.querySelector('#tx-list .txcard.sel'))return 'whole';if(document.querySelector('#tx-list .mrow.bsel'))return 'part';
      /* A9: Scratch/Log/Inbox whole-card select → Attach (no sub-select, so never 'part') */
      const list=activeFeedList();if(list&&list.id!=='tx-list'&&list.querySelector('.fcard.sel'))return 'whole';
      return null;}
    if(host==='hist'){return document.querySelector('#hist-list .fcard.sel')?'whole':null;}
    if(host.indexOf('asset-')===0)return 'whole';   /* an Asset is always attachable as a file */
    const sel=SELby[host];if(!sel)return null;return sel.kind==='all'?'whole':'part';}
  /* R-batch items 6-10: gate every item of the merged Export control per the current selection.
     Embed = any selection (item 7); Attach = whole-only; Copy / Export-to-file = whole card(s) on feed/hist,
     any line/section/doc selection in the editor (doc/plan); Assets are Attach-only (an image isn't copyable-as-
     text, embeddable as a quote, or a .md). The trigger enables if ANY item does. */
  function eaUpdate(host){const grp=document.querySelector('.ea-dd[data-eahost="'+host+'"]');if(!grp)return;
    const isAsset=host.indexOf('asset-')===0, isFeedHist=(host==='feed'||host==='hist');
    const kind=eaSelKind(host);
    const enEmbed=!isAsset&&!!kind, enAttach=kind==='whole';
    const enCopy=isAsset?false:(isFeedHist?kind==='whole':!!kind), enFile=enCopy;
    const set=(mode,on)=>{const b=grp.querySelector('[data-eamode="'+mode+'"]');if(b)b.disabled=!on;};
    set('copy',enCopy);set('file',enFile);set('embed',enEmbed);set('attach',enAttach);
    const btn=grp.querySelector('.exp-btn');if(btn)btn.disabled=!(enCopy||enFile||enEmbed||enAttach);}
  function eaUpdateAll(){document.querySelectorAll('.ea-dd[data-eahost]').forEach(g=>eaUpdate(g.dataset.eahost));}
  function eaSend(btn){const grp=btn.closest('.ea-dd');if(!grp||btn.disabled)return;const host=grp.dataset.eahost;closeAllPopups();
    const mode=btn.dataset.eamode;
    if(mode==='copy')expCopy(host);else if(mode==='file')expFile(host);else if(mode==='embed')eaEmbed(host);else if(mode==='attach')eaAttach(host);}
  function libSourceLabel(host){const e=entryById(host);if(!e)return 'Library';   /* L1: read the doc path/title off the DOCS/PLANS entry (the .docdoc panes are retired) */
    return host.indexOf('doc-')===0?('Library → Documents · '+e.path.split('/').pop()):('Library → Plans · '+e.title);}
  function editorSelText(host){const s=SELby[host];if(s&&s.kind==='box')return s.boxText||'';   /* L3 (5c): a popover box selection carries its own picked text */
    const ed=document.querySelector('[data-edhost="'+host+'"]');if(!ed)return '';
    const rows=[...ed.querySelectorAll('.md-row.rsel,.md-row.rsel-sec')];
    return rows.map(r=>{const l=r.querySelector('.md-line');return l?l.textContent:'';}).join('\n').trim();}
  /* R-batch item 6: Copy / Export-to-file for the merged control. feed/hist reuse feedExport/histExport (whole
     cards); editor hosts (doc-* or plan) act on the selected line/section/doc text. */
  function expCopy(host){if(host==='feed')return feedExport('copy-sel');if(host==='hist')return histExport('copy-sel');
    const txt=editorSelText(host);if(!txt){toast('Select something first');return;}
    if(navigator.clipboard)navigator.clipboard.writeText(txt).catch(()=>{});toast('Copied the selection');}
  function expFile(host){if(host==='feed')return feedExport('file-sel');if(host==='hist')return histExport('file-sel');
    const txt=editorSelText(host);if(!txt){toast('Select something first');return;}
    const base=(host.indexOf('doc-')===0?host.replace('doc-',''):host);
    const fname=base+'-export-'+(new Date().toTimeString().slice(0,5).replace(':',''))+'.md';
    addDocPaste(txt,fname);toast('Exported the selection → Documents · '+fname);}
  function eaEmbed(host){
    if(host==='feed'){if(eaSelKind('feed')==='part')return eaEmbedFeed();return embedWholeCards('feed');}   /* item 7: a block run embeds the blocks; a whole feed card embeds its full text */
    if(host==='hist')return embedWholeCards('hist');   /* item 7: History whole-card embed (was a no-op before) */
    const sel=SELby[host];if(!sel)return;const text=editorSelText(host);
    insertEmbed(libSourceLabel(host)+' · '+sel.label,text,"switchTab('doc','"+(host.indexOf('doc-')===0?'documents':'plan')+"')");}
  /* item 7: embed each selected WHOLE feed/History card as a frozen quoted block (full card text via cardText) */
  function embedWholeCards(host){const root=host==='hist'?document.getElementById('hist-list'):activeFeedList();if(!root)return;
    const cards=[...root.querySelectorAll('.fcard.sel')];if(!cards.length)return;
    cards.forEach(c=>{const txt=cardText(c);if(!txt)return;let src;
      if(host==='hist')src='Prompts → History';
      else{const o=c.classList.contains('txcard')?MSGS[+c.dataset.msgi]:null;const a=o?AG[o.ag]:null;src=a?('Feed · '+a.role+' '+a.name):'Feed';}
      insertEmbed(src,txt,host==='hist'?"switchTab('prompt','history')":"switchTab('feed','transcript')");});}
  function eaEmbedFeed(){const rows=[...document.querySelectorAll('#tx-list .mrow.bsel')].filter(r=>!r.classList.contains('mrow--title'));if(!rows.length)return;
    const card=rows[0].closest('.txcard');const o=MSGS[+card.dataset.msgi];const a=AG[o.ag];
    /* A7: multi-select → embed the combined text of every selected block (in document order) as one quoted block */
    const text=rows.map(r=>((r.querySelector('.mrow-c')||{}).textContent||'').trim()).filter(Boolean).join('\n\n');
    const kinds=rows.map(r=>r.dataset.mblk==='text'?'message':(r.dataset.blk||'block'));
    const label=kinds.length>1?(kinds.length+' blocks'):kinds[0];
    insertEmbed('Feed · '+a.role+' '+a.name+' · '+label,text,"switchTab('feed','transcript')");}
  function insertEmbed(src,text,srcAction){const f=document.getElementById('compose-field');if(!f)return;
    switchTab('prompt','compose');
    f.insertAdjacentHTML('beforeend',blockHTML('embed',{source:src,body:esc(text),srcAction:srcAction,clamp:text.length>220,kindLabel:'embed'}));
    if(window.lucide&&lucide.createIcons)lucide.createIcons();toast('Embedded into the Editor');}
  /* R-batch item 8: "Attach as file" SAVES the selection as a real file, drops a path chip into the prompt, then
     switches to Compose and reveals the chip. Materialized content (feed messages, History prompts) is written to a
     NEW Library → Documents doc (silent createDoc — distinct from "Export → file", which leaves you IN Documents);
     content that already has a real file (Assets, Documents, Plans) is chipped at its own path. */
  function eaAttach(host){
    if(host==='feed')return eaAttachFeed();
    if(host==='hist'){const cards=[...document.querySelectorAll('#hist-list .fcard.sel')];if(!cards.length)return;
      cards.forEach((c,k)=>{const txt=cardText(c);const fname='history-'+(new Date().toTimeString().slice(0,5).replace(':',''))+(cards.length>1?'-'+(k+1):'')+'.md';const d=createDoc(txt,fname);addAttachment({id:nextAttId(),name:d.name,path:d.path,type:'doc'});});
      revealAttachment();toast('Attached '+cards.length+' prompt'+(cards.length>1?'s':'')+' → saved to Documents');return;}
    let name,path,type='doc';
    if(host.indexOf('asset-')===0){const a=ASSETS.find(x=>'asset-'+x.id===host);if(!a)return;name=a.name;path=a.path;type='asset';}
    else if(host.indexOf('doc-')===0){const e=entryById(host);if(!e)return;path=e.path;name=e.path.split('/').pop();type='doc';}   /* L1: doc path off the DOCS entry */
    else {const p=PLANS.find(x=>x.id===host);if(!p)return;name=p.file;path='~/.claude/plans/'+p.file;type='doc';}
    addAttachment({id:nextAttId(),name:name,path:path,type:type});revealAttachment();toast('Attached '+name+' — path reference in the prompt');}
  /* A9: active feed list (Messages/Scratch/Log/Inbox) — the visible one drives the shared select-to-act strip */
  function activeFeedList(){const t=currentFeedTab();return document.getElementById({transcript:'tx-list',scratch:'scratch-list',log:'log-list',inbox:'inbox-list'}[t]||'tx-list');}
  function eaAttachFeed(){
    const list=activeFeedList();const tab=currentFeedTab();const cards=list?[...list.querySelectorAll('.fcard.sel')]:[];if(!cards.length)return;
    cards.forEach((card,k)=>{const txt=cardText(card);let base;
      if(card.classList.contains('txcard')){const o=MSGS[+card.dataset.msgi];const a=AG[o.ag];base=a.name+'-msg-'+o.time.replace(/:/g,'');}
      else base=tab+'-'+(k+1);
      const d=createDoc(txt,base+'.md');addAttachment({id:nextAttId(),name:d.name,path:d.path,type:'doc'});});
    revealAttachment();toast('Attached '+cards.length+' '+tab+' card'+(cards.length>1?'s':'')+' → saved to Documents');}
  /* item 8: end the attach flow on Compose with the new chip flashed so the user sees it land */
  function revealAttachment(){switchTab('prompt','compose');const strip=document.getElementById('attach-strip');if(!strip)return;
    const last=strip.querySelector('.att-card:last-child');if(!last)return;
    last.scrollIntoView({block:'nearest',inline:'nearest'});last.classList.remove('att-flash');void last.offsetWidth;last.classList.add('att-flash');setTimeout(()=>last.classList.remove('att-flash'),1000);}

  /* ============================ P4b — inline citations ============================ */
  /* From a chip's link icon, with the cursor in the prose, insert a citation pill carrying the attachment's
     path. Deleting a citation does NOT delete the attachment; deleting an attachment cascades to its citations;
     you can only cite something already attached (the trigger lives on the chip). */
  function citeAttachment(e,i){if(e)e.stopPropagation();const at=ATTACH[i];if(!at)return;
    const f=document.getElementById('compose-field');if(!f){toast('Open the Editor first');return;}
    switchTab('prompt','compose');
    const pill=citeHTML({att:at.id,source:at.path,label:at.name});
    const frag=document.createRange().createContextualFragment(pill+' ');
    if(composeRange&&f.contains(composeRange.commonAncestorContainer)){composeRange.collapse(false);composeRange.insertNode(frag);}
    else f.appendChild(frag);
    if(window.lucide&&lucide.createIcons)lucide.createIcons();toast('Cited '+at.name+' in the prose');}
  function onAttachmentRemoved(at){if(!at)return;const f=document.getElementById('compose-field');if(!f)return;
    f.querySelectorAll('.ed-cite[data-att="'+at.id+'"]').forEach(c=>c.remove());}   /* cascade: remove this attachment's citations */

  /* ============================ P4c — the Review chip (single-agent reviewer select) ============================ */
  const REVIEWERS={};
  function reviewChipHTML(planId){const k=REVIEWERS[planId]||'vega';const a=AG[k];
    return '<div data-comp="review-chip" data-status="planned" class="rev-chip" data-revchip="'+planId+'">'
      +'<button class="rev-trig" type="button" onclick="toggleRevPop(this)" title="Choose the reviewer">'+badgeHTML(a)+'<i data-lucide="chevrons-up-down" class="picker-cv"></i></button>'
      +'<div class="src-pop rev-pop"><div class="src-pop-head"><span class="sec-h" style="margin:0">Reviewer</span></div><div class="aglist aglist-scroll" style="max-height:220px">'+AG_ORDER.filter(x=>x!=='user').map(x=>revRowHTML(planId,x,x===k)).join('')+'</div></div>'
      +'<button data-status="planned" class="rev-act" type="button" onclick="sendReview(this)" title="Send this plan for review"><i data-lucide="scan-search"></i></button></div>';}   /* planned: sendReview is toast-only */
  function revRowHTML(planId,k,on){const a=AG[k];return '<button class="agrow'+(on?' on':'')+'" type="button" onclick="pickReviewer(this,\''+planId+'\',\''+k+'\')">'+agtileHTML(a)+'<span class="ag-lab"><span class="ag-role">'+a.role+'</span><span class="ag-name">'+a.name+'</span></span><i data-lucide="check" class="ag-ck"></i></button>';}
  function toggleRevPop(btn){const dd=btn.closest('.rev-chip');if(!dd)return;const pop=dd.querySelector('.rev-pop');const open=pop.classList.contains('open');closeAllPopups();if(!open){pop.classList.add('open');const pc=btn.closest('.plan-card');if(pc)pc.classList.add('pop-open');}}   /* R11 item 5: release the enclosing plan-card's overflow clip so the downward dropdown isn't cut at the card edge */
  function pickReviewer(row,planId,k){REVIEWERS[planId]=k;const chip=row.closest('.rev-chip');
    chip.querySelectorAll('.aglist .agrow').forEach(r=>r.classList.remove('on'));row.classList.add('on');
    const trig=chip.querySelector('.rev-trig');trig.innerHTML=badgeHTML(AG[k])+'<i data-lucide="chevrons-up-down" class="picker-cv"></i>';
    closeAllPopups();LU();}
  function sendReview(btn){const chip=btn.closest('.rev-chip');if(!chip)return;const k=REVIEWERS[chip.dataset.revchip]||'vega';toast('Sent for review to '+AG[k].name);}

  /* ============================ P1a — the inserted-block primitive ============================ */
  /* One renderer, three kinds the Editor holds inline:
       embed    — frozen quoted content (a doc section / a message block): muted, a "from <source>" header,
                  click-to-source, a remove ×, clamp+expand when long. Not editable.
       template — the same shell but interactive/selectable; the active one's pills fill from Templates.
       citation — an inline pill in the prose pointing at an attachment chip.
     Boundary uses the card-outline colour (--border). Consumed by P2 (Reply reference block),
     P3 (templates / editor body) and P4 (embeds / citations). One primitive, three variants. */
  function blockHTML(kind,o){o=o||{};
    if(kind==='citation') return citeHTML(o);
    const isTpl=kind==='template';
    const fromCls='ed-block-from'+(o.srcAction?' clickable':'');
    const fromAttr=o.srcAction?(' role="button" tabindex="0" onclick="'+o.srcAction+'" title="Open source in the dashboard"'):'';
    const head='<div class="ed-block-head">'
      +'<span class="'+fromCls+'"'+fromAttr+'>from <b>'+esc(o.source||'source')+'</b></span>'
      +'<span class="flex-1"></span>'
      +(o.kindLabel?'<span class="ed-block-kind">'+esc(o.kindLabel)+'</span>':'')
      +'<button class="ed-block-x" type="button" onclick="removeBlock(event,this)" title="Remove block"><i data-lucide="x"></i></button></div>';
    const body='<div class="ed-block-body'+(o.clamp?' clamp':'')+'">'+(o.body||'')+'</div>'
      +(o.clamp?'<button class="ed-block-more" type="button" onclick="toggleBlockClamp(event,this)">Show more</button>':'');
    const cls='ed-block ed-block--'+kind+(isTpl&&o.active?' sel':'');
    const dataAttr=(isTpl?(' data-tpl="'+(o.tpl!=null?o.tpl:'')+'" onclick="selectTplBlock(this)"'):'')+(o.src?' data-src="'+esc(o.src)+'"':'');
    return '<div data-comp="inserted-block" data-variants="embed template clamp" class="'+cls+'" data-block="'+kind+'"'+dataAttr+' contenteditable="false">'+head+body+'</div>';}
  function citeHTML(o){o=o||{};return '<span data-comp="citation-pill" data-status="planned" class="ed-cite" contenteditable="false" data-att="'+esc(o.att||'')+'" onclick="gotoCitation(event,this)" title="Citation → '+esc(o.source||o.label||'attachment')+'"><i data-lucide="link"></i>'+esc(o.label||o.source||'source')+'</span>';}
  function removeBlock(e,btn){if(e&&e.stopPropagation)e.stopPropagation();const b=btn.closest('.ed-block');if(b)b.remove();}
  function toggleBlockClamp(e,btn){if(e&&e.stopPropagation)e.stopPropagation();const body=btn.previousElementSibling;if(!body)return;const clamped=body.classList.toggle('clamp');btn.textContent=clamped?'Show more':'Show less';}
  function selectTplBlock(el){ /* make this template block the active one (the Templates fill input drives it — wired in P3) */
    const host=el.closest('#compose-field')||document;host.querySelectorAll('.ed-block--template.sel').forEach(b=>b.classList.remove('sel'));el.classList.add('sel');
    if(typeof onTplBlockSelected==='function')onTplBlockSelected(el);}
  function gotoCitation(e,el){if(e)e.stopPropagation(); /* P4 wires routing to the cited attachment's source */ toast((el.getAttribute('title')||'Citation'));}

  /* ===== node selection — SELECTION DRIVES THE APP: clicking a card repaints the whole Agent panel
     (identity, config readouts, Ctx/Turns) + the Console from that focused agent. (scripted demo) ===== */
  let FOCUS='sandy';
  function agKeyFromNode(n){const d=(n&&n.dataset&&n.dataset.agent)||'';return d.split('-').pop();}
  function setSegActive(id,label){if(!label)return;const seg=document.getElementById(id);if(!seg)return;
    seg.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.textContent.trim().toLowerCase()===label.toLowerCase()));}
  /* Launch-gated Bypass/Auto (§ Launch permissions): hide the mode-ring segments the agent didn't pre-arm at
     launch — SILENTLY absent (.seg-unarmed → display:none), never a greyed no-op. Applied to the Details ring
     on every repaint from the focused agent's armed[] flags. */
  function applyArmGate(seg,armed){if(!seg)return;armed=armed||[];
    seg.querySelectorAll('button[data-mode]').forEach(b=>b.classList.toggle('seg-unarmed',armed.indexOf(b.dataset.mode)<0));}
  function nodeBarRaw(n,label){const rows=[...n.querySelectorAll('.nbar-row')];const r=rows.find(x=>{const l=x.querySelector('.nbl');return l&&l.textContent.trim()===label;});
    if(!r)return null;const i=r.querySelector('.pbar i');const pct=i?parseFloat(i.style.width):null;const val=(r.querySelector('.nbv')||{}).textContent||'';return{pct:pct,val:val};}
  function repaintConsoleIdentity(a){document.querySelectorAll('.con-agentbar').forEach(bar=>{const t=bar.querySelector('.agtile');if(t){t.style.color=a.color;const u=t.querySelector('use');if(u)u.setAttribute('href','#'+a.icon);}
    const r=bar.querySelector('[data-con-role]');if(r)r.textContent=a.role;const nm=bar.querySelector('[data-con-name]');if(nm)nm.textContent=a.name;});
    if(CON_FEED&&CON_FEED.length)CON_FEED[0].t=a.role+' · '+a.name+' — claude-code v2.0.14 · model: opus 4.8 · cwd: ~/agent-dashboard';}
  function repaintAgentPanel(n,key){const a=AG[key];if(!a)return;
    const tile=document.getElementById('det-tile');if(tile){tile.style.color=a.color;const u=tile.querySelector('use');if(u)u.setAttribute('href','#'+a.icon);}
    const role=document.getElementById('det-role');if(role)role.textContent=a.role;
    const name=document.getElementById('det-name');if(name)name.textContent=a.name;
    const cr=document.getElementById('det-created');if(cr&&a.created)cr.textContent=a.created;
    const nb=n.querySelector('.node-badge');const db=document.getElementById('det-badge');
    if(nb&&db){const cl=[...nb.classList].find(c=>/^nb-/.test(c))||'nb-idle';db.className='node-badge '+cl+' det-badge';db.textContent=nb.textContent;
      const st=cl==='nb-pending'?'pending':(cl==='nb-active'?'active':(cl==='nb-error'?'error':'idle'));db.setAttribute('onclick','statusJump(\''+st+'\')');db.title=nb.title;}   /* R-batch item 1: map nb-error → the 'error' jump (→ Inbox) too */
    const meta=((n.querySelector('.node-meta')||{}).textContent||'').replace(/\s+/g,' ').trim();const parts=meta.split('·').map(s=>s.trim());
    const mc=document.getElementById('model-current');if(mc&&parts[0])mc.textContent=parts[0];
    setSegActive('mode-seg',parts[1]);setSegActive('effort-seg',parts[2]);
    applyArmGate(document.getElementById('mode-seg'),a.armed);   /* un-armed Bypass/Auto vanish from the focused agent's ring */
    const tt=document.getElementById('det-think');if(tt)tt.classList.toggle('on',/think on/i.test(meta));
    const ctx=nodeBarRaw(n,'Ctx');if(ctx&&ctx.pct!=null){const cb=document.getElementById('ctx-bar');if(cb)cb.innerHTML='<i style="width:'+ctx.pct+'%;background:'+ctxColor(ctx.pct)+'"></i>'+cutHTML();
      const cp=document.getElementById('det-ctx-pct');if(cp)cp.textContent=Math.round(ctx.pct)+'%';}
    const tr=nodeBarRaw(n,'Turns');if(tr){const th=document.getElementById('det-turns');if(th&&tr.val)th.textContent=tr.val;
      const tb=document.getElementById('det-turns-bar');if(tb&&tr.pct!=null)tb.innerHTML='<i style="width:'+tr.pct+'%;background:'+ctxColor(tr.pct)+'"></i>';
      const tp=document.getElementById('det-turns-pct');if(tp&&tr.pct!=null)tp.textContent=Math.round(tr.pct)+'%';}
    /* keep the editable identity config fields coherent with the focused agent (role/no/name/color/icon) */
    const det=document.getElementById('mid-details');
    if(det){const mm=a.name.match(/^(\d+)\s+(.+)$/);const no=mm?mm[1]:'';const nm=mm?mm[2]:a.name;
      const roleIn=det.querySelector('.combo-in');if(roleIn)roleIn.value=a.role;
      const noIn=det.querySelector('input.in.text-center');if(noIn)noIn.value=no;
      const nameIn=[...det.querySelectorAll('input.in')].find(i=>!i.classList.contains('text-center'));if(nameIn)nameIn.value=nm;
      const cf=det.querySelector('[style*="--cur-color"]');if(cf)cf.style.setProperty('--cur-color',a.color);
      const sw=det.querySelector('[data-picker]:not([data-icopicker]) .picker-sw');if(sw)sw.style.background=a.color;
      const colNm=(a.color.match(/--ag-([a-z]+)/)||[])[1];const colVal=det.querySelector('[data-picker]:not([data-icopicker]) .picker-val');if(colVal&&colNm)colVal.textContent=colNm;
      const icoUse=det.querySelector('[data-icopicker] .picker-ico use');if(icoUse)icoUse.setAttribute('href','#'+a.icon);
      const icoNm=(AGENT_ICONS.find(p=>p[0]===a.icon)||[])[1];const icoVal=det.querySelector('[data-icopicker] .picker-val');if(icoVal&&icoNm)icoVal.textContent=icoNm;}
    repaintConsoleIdentity(a);
    if(typeof tlSetMode==='function')tlSetMode(null);}   /* the Timeline repaints per focused agent; an armed Rewind/Handoff resets on focus change */
  function selectNode(n){
    document.querySelectorAll('.node').forEach(x=>x.classList.remove('selected'));
    n.classList.add('selected');
    const key=agKeyFromNode(n);if(AG[key])FOCUS=key;
    repaintAgentPanel(n,key);LU();
  }

  /* ===== pickers (Color = Select · Icon = Combobox) ===== */
  const AGENT_ICONS=[
    ['ag-wizard','wizard-face'],['ag-golem','metal-golem-head'],['ag-gasmask','gas-mask'],['ag-robot','robot-helmet'],
    ['ag-fox','fox-head'],['ag-spider','spider-mask'],['ag-eagle','eagle-head'],['ag-centurion','centurion-helmet'],
    ['ag-parrot','parrot-head'],['ag-tribal','tribal-mask'],['ag-astronaut','astronaut-helmet'],['ag-thirdeye','third-eye'],
    ['ag-cowled','cowled'],['ag-wolf','wolf-head'],['ag-bear','bear-head'],['ag-tiger','tiger-head'],['ag-dragon','dragon-head'],
    ['ag-skull','skull-mask'],['ag-ninja','ninja-head'],['ag-viking','viking-head'],['ag-samurai','samurai-helmet'],
    ['ag-oni','oni'],['ag-goblin','goblin-head'],['ag-ogre','ogre'],['ag-vampire','vampire-dracula'],['ag-witch','witch-face'],
    ['ag-pumpkin','pumpkin-mask'],['ag-cyborg','cyborg-face'],['ag-mecha','mecha-head'],
    ['ag-stag','stag-head'],['ag-elephant','elephant-head'],['ag-raccoon','raccoon-head'],['ag-rabbit','rabbit-head'],['ag-buffalo','buffalo-head'],['ag-minotaur','minotaur'],['ag-medusa','medusa-head'],['ag-orc','orc-head'],['ag-troll','troll'],['ag-imp','imp-laugh'],['ag-spectre','spectre'],['ag-spartan','spartan-helmet'],['ag-knight','black-knight-helm'],['ag-pirate','pirate-captain'],['ag-plague','plague-doctor-profile'],['ag-clown','clown'],['ag-monk','monk-face'],['ag-android','android-mask'],['ag-samus','samus-helmet'],['ag-deathskull','death-skull'],['ag-squid','squid-head']];
  function buildIconGrids(){
    const html=AGENT_ICONS.map(([id,nm])=>'<button class="icotile" data-name="'+nm+'" title="'+nm+'" onclick="pickIconChoice(this)"><span class="agtile" style="color:var(--cur-color)"><svg class="ag-svg"><use href="#'+id+'"/></svg></span></button>').join('');
    document.querySelectorAll('[data-icogrid]').forEach(g=>g.innerHTML=html);
    document.querySelectorAll('[data-icopicker] .picker-search input').forEach(s=>s.setAttribute('placeholder','Search '+AGENT_ICONS.length+' icons…'));   /* honest count from the embedded sprite set */
  }
  function curColorHost(el){let p=el;while(p&&p!==document.body){if(p.style&&p.style.getPropertyValue('--cur-color'))return p;p=p.parentElement;}return null;}
  function togglePicker(btn){
    const pick=btn.closest('.picker'),pop=pick.querySelector('.picker-pop');const open=pop.classList.contains('open');
    closeAllPopups(); if(open)return;
    const r=btn.getBoundingClientRect(); pop.classList.toggle('up', r.bottom>window.innerHeight-260);
    pop.classList.add('open');
    const s=pop.querySelector('.picker-search input'); if(s){s.value='';filterIconsGrid(pop,'');setTimeout(()=>s.focus({preventScroll:true}),0);}
  }
  function pickColor(el){
    const grid=el.closest('[data-colorgrid]');grid.querySelectorAll('.sw').forEach(s=>s.classList.remove('on'));el.classList.add('on');
    const pick=el.closest('.picker');pick.querySelector('.picker-sw').style.background=el.style.background;pick.querySelector('.picker-val').textContent=el.dataset.name;
    const host=curColorHost(pick); if(host)host.style.setProperty('--cur-color',el.style.background);
    pick.querySelector('.picker-pop').classList.remove('open');
  }
  function pickIconChoice(el){
    const pop=el.closest('.picker-pop'),pick=el.closest('.picker');
    pop.querySelectorAll('.icotile').forEach(t=>t.classList.remove('on'));el.classList.add('on');
    const href=el.querySelector('use').getAttribute('href');
    pick.querySelector('.picker-ico use').setAttribute('href',href);
    pick.querySelector('.picker-val').textContent=el.dataset.name;
    pop.classList.remove('open');
  }
  function filterIconsGrid(pop,q){const g=pop.querySelector('[data-icogrid]');if(!g)return;q=q.toLowerCase();g.querySelectorAll('.icotile').forEach(t=>{t.style.display=t.dataset.name.toLowerCase().includes(q)?'':'none';});}
  function filterIcons(input){filterIconsGrid(input.closest('.picker-pop'),input.value);}

  /* ===== MODEL button groups ===== */
  /* NU-7: the Claude-Code-default "Inherit" entry is retired — the app defines its own default (Opus, the
     markup's active tab in both bands); a Handoff prefills the SOURCE agent's concrete model instead. */
  const MODELS={opus:['4.8','4.6','4.5','4.1'],sonnet:['4.6','4.5','3.7'],haiku:['4.5','3.5'],fable:['5']};
  const DEFV={opus:'4.8',sonnet:'4.6',haiku:'4.5',fable:'5'};
  /* v1.x #2: Fast (/fast) is Opus-only — gate a panel's Fast toggle whenever its selected model isn't Opus */
  function gateFast(tabs){const panel=tabs.closest('[data-group="mid"]');if(!panel)return;const ft=panel.querySelector('.fast-tog');if(!ft)return;
    const m=((tabs.querySelector('.model-tab.active')||{}).dataset||{}).model;const ok=m==='opus';
    ft.classList.toggle('gated',!ok);ft.disabled=!ok;ft.setAttribute('aria-disabled',String(!ok));if(!ok){ft.classList.remove('on');const l=ft.querySelector('.tt-lbl');if(l)l.textContent='Opus Fast-Mode Off';}
    ft.title=ok?'Opus fast mode (/fast) — faster responses, slightly lower quality':'Fast mode (/fast) is Opus-only — select Opus to enable';}
  document.querySelectorAll('.model-tabs').forEach(tabs=>{
    const wrap=tabs.parentElement,ver=tabs.nextElementSibling,curEl=wrap.querySelector('#model-current,.model-cur');
    const act=tabs.querySelector('.model-tab.active');
    const st={model:act?act.dataset.model:'opus',ver:Object.assign({},DEFV)};
    const label=()=>st.model+' '+st.ver[st.model];   /* NU-7: the 'inherit ← parent' branch is retired with the Inherit tab */
    function renderVer(){const vs=MODELS[st.model]||[];if(!vs.length){ver.classList.remove('open');ver.innerHTML='';return;}
      ver.innerHTML=vs.map(v=>'<div class="ver-row'+(v===st.ver[st.model]?' sel':'')+'" data-v="'+v+'"><span class="ver-name">'+st.model+'-'+v+'</span><span class="ver-check">✓</span></div>').join('');
      ver.querySelectorAll('.ver-row').forEach(r=>r.onclick=()=>{st.ver[st.model]=r.dataset.v;if(curEl)curEl.textContent=label();ver.classList.remove('open');renderVer();});
      ver.classList.add('open');}
    tabs.querySelectorAll('.model-tab').forEach(t=>t.onclick=()=>{const m=t.dataset.model;if(st.model===m&&ver.classList.contains('open')){ver.classList.remove('open');return;}st.model=m;tabs.querySelectorAll('.model-tab').forEach(x=>x.classList.toggle('active',x===t));if(curEl)curEl.textContent=label();renderVer();gateFast(tabs);});
    /* NU-7: programmatic setter for the band (used by the Handoff prefill — prefillFromFocus sets the Create
       band to the SOURCE agent's model). Mirrors a tab click minus opening the version popout. */
    tabs._set=(m,v)=>{if(!MODELS[m])return;st.model=m;if(v&&MODELS[m].indexOf(v)>=0)st.ver[m]=v;
      tabs.querySelectorAll('.model-tab').forEach(x=>x.classList.toggle('active',x.dataset.model===m));
      if(curEl)curEl.textContent=label();ver.classList.remove('open');gateFast(tabs);};
    if(curEl)curEl.textContent=label();
    gateFast(tabs);   /* v1.x #2: set the Fast gate from the panel's initial model */
  });

  /* ===== CONTEXT breakdown ===== */
  const CTX={model:'claude-opus-4-8',used:'399.1k',total:'1.0M',pct:40,cats:[
    {nm:'System prompt',tk:'1.5k',pc:'0.2%',c:'var(--ag-azure)'},{nm:'System tools',tk:'5.1k',pc:'0.5%',c:'var(--ag-cyan)'},
    {nm:'MCP tools',tk:'27.5k',pc:'2.8%',c:'var(--ag-fern)'},{nm:'Custom agents',tk:'1.8k',pc:'0.2%',c:'var(--warning)'},
    {nm:'Memory files',tk:'10.8k',pc:'1.1%',c:'var(--ag-violet)'},{nm:'Messages',tk:'352.4k',pc:'35.2%',c:'var(--main)'},
    {nm:'Free space',tk:'600.9k',pc:'60.0%',c:'var(--rule)'}]};
  const MEMF=[{p:'~\\.claude\\CLAUDE.md',t:'8.8k'},{p:'~\\MeDocuments\\…\\CLAUDE.md',t:'2.1k'}];
  const ACTX=[{n:'superpowers:code-reviewer',t:'348'},{n:'vibe-guide',t:'93'},{n:'gsd-ui-researcher',t:'86'}];
  /* v9p7 (A1): context cutoff — the per-agent Context% auto-stop default. Bars gray out everything above it. */
  window.CTX_CUTOFF=80;
  const cutHTML=()=>'<span class="bar-cut" style="left:'+window.CTX_CUTOFF+'%"></span>';
  /* Next-up item 6 — Context turn-scope select. The breakdown head's model text becomes a native
     <select> (Total / Turn n…1 descending, n = the agent's turn count). The head, bar, and category
     rows RESCOPE to the chosen turn; the two sub-sections ("/ Memory files" + "/ Custom agents")
     describe what's LOADED in context (loaded once, not per-turn), so they stay put across scopes. */
  const CTX_NTURNS=34;   /* same source as the Turns "34/50" readout */
  /* Per-turn contribution (DEMO). Same category vocab as Total: a turn's NEW tokens are mostly
     Messages, with the odd MCP result / memory (re)load — scoped to that turn (no Free space). */
  function ctxTurnData(n){
    const msgsK=7+((n*37)%19);                       /* 7..25k Messages */
    const mcpK=(n%3===0)?1+((n*13)%4):0;             /* some turns pull a big MCP result */
    const memK=(n%8===0)?1.2:0;                       /* rare memory (re)load */
    const cats=[{nm:'Messages',k:msgsK,c:'var(--main)'}];
    if(mcpK)cats.push({nm:'MCP tools',k:mcpK,c:'var(--ag-fern)'});
    if(memK)cats.push({nm:'Memory files',k:memK,c:'var(--ag-violet)'});
    const totK=cats.reduce((s,c)=>s+c.k,0);
    return {totK,cats};
  }
  const barHTML=()=>CTX.cats.map(c=>'<i style="width:'+parseFloat(c.pc)+'%;background:'+c.c+'"></i>').join('');
  /* the two sub-sections — identical across scopes (loaded context, not a per-turn quantity) */
  const ctxSubsHTML=()=>'<div class="bd-sub"><h5>/ Memory files</h5>'+MEMF.map(m=>'<div class="ml"><span class="p">'+m.p+'</span><span class="t">'+m.t+'</span></div>').join('')+'</div>'
    +'<div class="bd-sub"><h5>/ Custom agents</h5>'+ACTX.map(a=>'<div class="ml"><span class="p">'+a.n+'</span><span class="t">'+a.t+'</span></div>').join('')+'</div>';
  /* static shell — the head <select> + empty containers the scope renderer fills.
     (.bd-rows marks the stale-dimmable row containers for the .is-loading pull state — Next-up item 1) */
  function breakdownHTML(){return '<div data-comp="context-breakdown" data-variants="is-loading" class="bd"><div class="bd-head bd-head--scope"><select data-comp="scope-select" class="bd-scope" id="ctx-scope" aria-label="Context scope"></select><span class="bd-tot" id="ctx-bd-tot"></span></div>'
    +'<div class="bd-bar" id="ctx-bd-bar"></div><div id="ctx-bd-cats" class="bd-rows"></div><div id="ctx-bd-subs" class="bd-rows"></div></div>';}
  const catRow=(c,nm,tk,pc)=>'<div class="cat"><span class="sw2" style="background:'+c+'"></span><span class="nm">'+nm+'</span><span class="tk">'+tk+'</span><span class="pc">'+pc+'</span></div>';
  function renderCtxTotal(){
    const tot=document.getElementById('ctx-bd-tot');if(!tot)return;
    tot.textContent=CTX.used+' / '+CTX.total+' · '+CTX.pct+'%';
    document.getElementById('ctx-bd-bar').innerHTML=barHTML()+cutHTML();   /* window cutoff applies */
    document.getElementById('ctx-bd-cats').innerHTML=CTX.cats.map(c=>catRow(c.c,c.nm,c.tk,c.pc)).join('');
    document.getElementById('ctx-bd-subs').innerHTML=ctxSubsHTML();
  }
  function renderCtxTurn(n){
    const tot=document.getElementById('ctx-bd-tot');if(!tot)return;const d=ctxTurnData(n);
    /* header: same metric type as Total, numerator = turn tokens, % = share of the 1.0M window (2 dp) */
    tot.textContent=d.totK.toFixed(1)+'k / '+CTX.total+' · '+(d.totK/10).toFixed(2)+'%';
    /* bar + rows: % of THIS turn (no Free space, no window cutoff) */
    document.getElementById('ctx-bd-bar').innerHTML=d.cats.map(c=>'<i style="width:'+(c.k/d.totK*100)+'%;background:'+c.c+'"></i>').join('');
    document.getElementById('ctx-bd-cats').innerHTML=d.cats.map(c=>catRow(c.c,c.nm,c.k.toFixed(1)+'k',(c.k/d.totK*100).toFixed(1)+'%')).join('');
    document.getElementById('ctx-bd-subs').innerHTML=ctxSubsHTML();   /* unchanged — loaded context */
  }
  (function(){const bar=document.getElementById('ctx-bar');if(bar)bar.innerHTML='<i style="width:'+CTX.pct+'%;background:'+ctxColor(CTX.pct)+'"></i>'+cutHTML();const panel=document.getElementById('ctx-panel');if(panel)panel.innerHTML=breakdownHTML();
    /* Next-up item 1 (design side) — ON-OPEN CONTEXT PULL. Context can't be read while an agent is
       mid-run, so opening the accordion triggers a direct pull; while it's in flight the breakdown
       shows the loading-state primitive (the bar swaps to the teal .loading-strip--fill shimmer and
       the stale rows/total dim via .bd.is-loading) until the fresh data renders. SIMULATED here with
       a brief delay — the real between-runs refresh + pull endpoint are backend work (see DESIGN.md);
       this is the design contract for that flow. Closing mid-flight cancels + restores cleanly. */
    let ctxPullT=null;
    const ctxRenderScope=()=>{const sc=document.getElementById('ctx-scope');(!sc||sc.value==='total')?renderCtxTotal():renderCtxTurn(+sc.value);};
    function ctxPullStart(){const bd=document.querySelector('#ctx-panel .bd');if(!bd)return;
      bd.classList.add('is-loading');
      const bar=document.getElementById('ctx-bd-bar');
      if(bar)bar.innerHTML='<span data-comp="loading-strip" data-variants="fill" class="loading-strip loading-strip--fill" title="Pulling fresh context…"></span>';
      clearTimeout(ctxPullT);
      ctxPullT=setTimeout(()=>{ctxPullT=null;bd.classList.remove('is-loading');ctxRenderScope();},650);}
    function ctxPullCancel(){clearTimeout(ctxPullT);ctxPullT=null;
      const bd=document.querySelector('#ctx-panel .bd');
      if(bd&&bd.classList.contains('is-loading')){bd.classList.remove('is-loading');ctxRenderScope();}}
    const btn=document.getElementById('ctx-btn');if(btn)btn.addEventListener('click',()=>{const p=document.getElementById('ctx-panel');const open=p.classList.toggle('open');btn.classList.toggle('open',open);const ch=document.getElementById('ctx-chev');if(ch)ch.classList.toggle('up',open);open?ctxPullStart():ctxPullCancel();});
    /* wire the scope select: Total + Turn n…1 descending */
    const sel=document.getElementById('ctx-scope');
    if(sel){sel.insertAdjacentHTML('beforeend','<option value="total">Total</option>');
      for(let n=CTX_NTURNS;n>=1;n--)sel.insertAdjacentHTML('beforeend','<option value="'+n+'">Turn '+n+'</option>');
      /* fit the native <select> to its CURRENT value (+ chevron) — a native select otherwise sizes to its
         widest option ("Turn 34"), so the short "Total" label would float left of the chevron. */
      const meas=document.createElement('span');
      meas.style.cssText='position:absolute;visibility:hidden;white-space:pre;font-family:var(--font-sans);font-weight:800;font-size:12px;';
      document.body.appendChild(meas);
      const fitCtxScope=()=>{meas.textContent=sel.options[sel.selectedIndex].text;sel.style.width=(meas.offsetWidth+17)+'px';};
      sel.addEventListener('change',e=>{fitCtxScope();const bd=document.querySelector('#ctx-panel .bd');
        if(bd&&bd.classList.contains('is-loading'))return;   /* item 1: mid-flight scope change renders when the pull lands (ctxRenderScope reads the select) */
        e.target.value==='total'?renderCtxTotal():renderCtxTurn(+e.target.value);});
      fitCtxScope();
      if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitCtxScope);   /* re-fit once the web font loads */
    }
    renderCtxTotal();})();

  /* ===== TURNS breakdown (Next-up item 1) ===== */
  /* The Turns bar becomes a Context-style dropdown: same .ctx-trigger + .acc + .bd chrome as Context,
     breaking the 34 turns out BY TOOL (Read/search · Edit · Bash · MCP · Subagent · Web) with a
     COORDINATING slice (the multi-agent angle), a "Remaining" segment closing the 50-turn budget
     (paralleling Context's "Free space"), and two drill-downs paralleling Context's sub-sections.
     This is the categorical summary; the per-turn chronological log is the Rewind/Handoff timeline below
     (whose demo records live in TL_ROWS_DEFAULT / TL_ROWS). */
  const TURNS_BD={subject:'sandy',tot:'34 / 50 · 68%',pct:68,cutoff:null,cats:[
    {nm:'Read / search',v:'10',pc:'20%',c:'var(--ag-azure)'},{nm:'Edit / Write',v:'8',pc:'16%',c:'var(--ag-emerald)'},
    {nm:'Bash',v:'6',pc:'12%',c:'var(--ag-gold)'},{nm:'Coordinating',v:'4',pc:'8%',c:'var(--ag-violet)'},
    {nm:'MCP tools',v:'3',pc:'6%',c:'var(--ag-cyan)'},{nm:'Subagent (Task)',v:'2',pc:'4%',c:'var(--ag-magenta)'},
    {nm:'Web',v:'1',pc:'2%',c:'var(--ag-citron)'},{nm:'Remaining',v:'16',pc:'32%',c:'var(--rule)'}],
    subs:[{h:'/ Tools used (calls)',items:[{p:'Read',t:'×18'},{p:'Edit',t:'×14'},{p:'Bash',t:'×9'},{p:'Grep',t:'×7'},{p:'mcp:playwright',t:'×5'},{p:'Task',t:'×2'}]},
      {h:'/ Coordinated with',items:[{p:'scratchpad (posts)',t:'×2'},{p:'auditor-01 (cross-check)',t:'×1'},{p:'coder-01 (patch review)',t:'×1'}]}]};
  const turnsCutHTML=co=>co==null?'':'<span class="bar-cut" style="left:'+co+'%"></span>';
  function turnsBreakdownHTML(D){
    const bar=D.cats.map(c=>'<i style="width:'+parseFloat(c.pc)+'%;background:'+c.c+'"></i>').join('');
    const cats=D.cats.map(c=>'<div class="cat"><span class="sw2" style="background:'+c.c+'"></span><span class="nm">'+c.nm+'</span><span class="tk">'+c.v+'</span><span class="pc">'+c.pc+'</span></div>').join('');
    const subs=D.subs.map(s=>'<div class="bd-sub"><h5>'+s.h+'</h5>'+s.items.map(m=>'<div class="ml"><span class="p">'+m.p+'</span><span class="t">'+m.t+'</span></div>').join('')+'</div>').join('');
    return '<div data-comp="turns-breakdown" class="bd"><div class="bd-head"><span class="bd-model">'+D.subject+'</span><span class="bd-tot">'+D.tot+'</span></div>'
      +'<div class="bd-bar">'+bar+turnsCutHTML(D.cutoff)+'</div>'+cats+subs+'</div>';
  }
  (function(){const panel=document.getElementById('turns-bd-panel');if(panel)panel.innerHTML=turnsBreakdownHTML(TURNS_BD);
    const btn=document.getElementById('turns-btn');if(btn)btn.addEventListener('click',()=>{const p=document.getElementById('turns-bd-panel');const open=p.classList.toggle('open');btn.classList.toggle('open',open);const ch=document.getElementById('turns-chev');if(ch)ch.classList.toggle('up',open);});})();

  /* ===== TIMELINE (the standing per-turn log — rewind / handoff) ===== */
  /* One row per DASHBOARD-INITIATED turn of the focused agent, from the per-agent per-turn record: the
     settings AT that turn (model + the agent-card mode/effort/thinking icon pairs — unknown fields honestly
     omitted; the rendered settings string rides the tooltip) and a one-line summary of the reply (a missing
     summary reads a muted "—", never a fabricated line). Row numbers are RECORD ordinals — deliberately not
     the Turns readout's model-round count — and terminal-driven turns never land in the record (the standing
     footnote + the rewind confirm carry that honest limit). Rewind addressing is k-FROM-LAST over these
     records: picking row n of N rolls back N−n prompts; Handoff from row n forks a new agent seeded through
     that turn (row N = fork at head). The summary vocabulary is shared with the Feed / History
     collapsed previews. */
  function ctxColor(p){return p<50?'var(--success)':(p<=75?'var(--warning)':'var(--danger)');}   /* the shared health scale — the card + Agent-panel context/turns bars key off it */
  const TL_ROWS_DEFAULT=[
    {n:1,time:'12:41',model:'sonnet 4.6',mode:'ask',effort:null,think:null,sum:'Scoped the audit — session handling first, then token rotation'},
    {n:2,time:'12:58',model:'sonnet 4.6',mode:'ask',effort:'med',think:'off',sum:'Mapped the auth module and its three token entry points'},
    {n:3,time:'13:22',model:'opus 4.8',mode:'ask',effort:'high',think:'on',sum:'Flagged JWT expiry unchecked on the refresh path'},
    {n:4,time:'13:40',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:null},
    {n:5,time:'14:05',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:'Posted CRITICAL token-rotation finding to the scratchpad'},
    {n:6,time:'14:28',model:'opus 4.8',mode:'auto',effort:'max',think:'on',sum:'Cross-checked the finding with auditor-01 — confirmed'},
    {n:7,time:'14:41',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:'Demoted the rate-limit finding to medium severity'},
    {n:8,time:'14:56',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:'Drafted the remediation plan — awaiting the deploy-gate decision',cur:true}];
  /* per-agent demo records + edge states (representative; the app repaints per focused agent): io = a young
     agent with no dashboard turns yet (empty) · max = mid-run (busy — actions wait for idle) · quinn = an
     older CLI below the ≥ 2.1.191 rewind/fork floor (gated) · lex = a non-repo cwd (exercises the handoff
     confirm's shared-cwd file-state note). Agents without their own rows show the default set, like the
     other repaint-per-focus readouts in this mockup. */
  const TL_ROWS={
    max:[
      {n:1,time:'13:12',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:'Reproduced the rotation bug behind the ECONNREFUSED'},
      {n:2,time:'13:48',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:'Patched refresh-token rotation + added a regression test'},
      {n:3,time:'14:31',model:'opus 4.8',mode:'auto',effort:'high',think:'on',sum:'Applying review feedback on the expiry-check patch',cur:true}],
    quinn:[
      {n:1,time:'09:02',model:'sonnet 4.6',mode:'plan',effort:'med',think:'off',sum:'Drafted the milestone plan skeleton'},
      {n:2,time:'09:36',model:'sonnet 4.6',mode:'plan',effort:'med',think:'off',sum:'Sequenced the phases against the dependency map'},
      {n:3,time:'10:04',model:'sonnet 4.6',mode:'plan',effort:'med',think:'off',sum:'Filed open questions for the roadmap review',cur:true}],
    io:[]};
  const TL_STATE={io:{state:'empty'},max:{state:'busy'},quinn:{state:'gated',cli:'2.1.184'},lex:{repo:false,cwd:'~/design-scratch'}};
  const TL_ANCHOR={};   /* per-agent post-rewind marker (agent → target turn n) — drives the no-anchor caveat state */
  let TL_MODE=null;     /* 'rewind' | 'handoff' | null (nothing armed — the list is a read-only log) */
  function tlRows(){return TL_ROWS[FOCUS]||TL_ROWS_DEFAULT;}
  function tlHead(){const r=tlRows();return r.length?r[r.length-1].n:0;}
  function tlChip(icon,title,val){return '<span class="node-chip" title="'+title+'"><i data-lucide="'+icon+'"></i>'+val+'</span>';}
  function tlSetHTML(t){const str=[t.model,t.mode,t.effort?'effort '+t.effort:null,t.think!=null?'thinking '+t.think:null].filter(Boolean).join(' · ');
    return '<span class="tl-set" title="'+str+'">'+t.model
      +(t.mode?tlChip('shield','Permission mode',t.mode):'')
      +(t.effort?tlChip('gauge','Reasoning effort',t.effort):'')
      +(t.think!=null?tlChip('brain','Extended thinking',t.think):'')+'</span>';}
  function tlNoteHTML(kind,icon,text){return '<div class="tl-note tl-note--'+kind+'"><i data-lucide="'+icon+'"></i><span>'+text+'</span></div>';}
  function tlRowTitle(t,N){if(!TL_MODE)return 'Arm Rewind or Handoff above to act from this turn';
    if(TL_MODE==='rewind')return t.n===N?'Already the head — rewinding here is a no-op':'Rewind to the end of this turn';
    return t.n===N?'Hand off from here (fork at head)':'Hand off from the end of this turn';}
  function tlRowHTML(t,N){const rolled=TL_ANCHOR[FOCUS]!=null&&t.n>TL_ANCHOR[FOCUS];
    return '<div class="tl-row'+(t.cur?' current':'')+(rolled?' tl-row--rolled':'')+'" role="button" tabindex="0" title="'+tlRowTitle(t,N)+'" onclick="tlPick('+t.n+')">'
      +'<div class="tl-main"><div class="tl-top"><span class="tl-turn">'+t.n+'</span>'
      +(t.cur?'<span class="tl-now">now</span>':'')+(rolled?'<span class="tl-rolltag">rolled back</span>':'')
      +tlSetHTML(t)+'<span class="tl-time">'+t.time+'</span></div>'
      +(t.sum?'<div class="tl-desc">'+t.sum+'</div>':'<div class="tl-desc tl-desc--none">— no summary recorded</div>')+'</div></div>';}
  function renderTimeline(){const panel=document.getElementById('hist-panel');if(!panel)return;
    const a=AG[FOCUS]||{name:'agent'};const st=TL_STATE[FOCUS]||{};const anchor=TL_ANCHOR[FOCUS];
    /* the four state notes are always emitted (hidden); the .tl root's state class shows the matching one.
       Note kinds ≠ state names on purpose (fresh/running/version/anchor) — see the styles.css note. */
    let html=tlNoteHTML('fresh','history','No turns yet — a row lands here as each dashboard-initiated turn completes.')
      +tlNoteHTML('running','clock',esc(a.name)+' is mid-run — Rewind &amp; Handoff need an idle agent. The log stays readable; the actions return when the run completes.')
      +tlNoteHTML('version','lock','Rewind &amp; Handoff need Claude Code ≥ 2.1.191 — this agent is running '+(st.cli||'an older CLI')+'. Relaunch it on a newer version to enable both.')
      +tlNoteHTML('anchor','triangle-alert','Rewound to the end of Turn '+(anchor!=null?anchor:'n')+' — records carry no rewind anchor, so the rolled-back rows stay in the log (dimmed) and new turns will append after them.');
    html+=tlRows().map(t=>tlRowHTML(t,tlHead())).join('');
    html+='<div class="tl-foot">Dashboard-initiated turns only — turns driven from a raw terminal aren&#8217;t recorded and can&#8217;t be targeted.</div>';
    panel.innerHTML=html;
    panel.className='tl'+(st.state?' tl--'+st.state:'')+(anchor!=null?' tl--no-anchor':'')+(TL_MODE?' tl--armed tl--'+TL_MODE:'');
    const tabs=document.getElementById('hist-tabs');
    if(tabs){tabs.classList.toggle('tri-tabs--gated',st.state==='gated');
      tabs.title=st.state==='gated'?'Needs Claude Code ≥ 2.1.191 — this agent runs '+(st.cli||'an older CLI'):'';}
    LU();
    /* a visible state note is a lead-in strip — keep it on screen (scroll top); otherwise follow the head row */
    if(st.state||anchor!=null){panel.scrollTop=0;}
    else{const cur=panel.querySelector('.tl-row.current');if(cur)panel.scrollTop=Math.max(0,cur.offsetTop-8);}}
  function tlSetMode(m){TL_MODE=m;
    document.querySelectorAll('#hist-tabs .tri-tab').forEach(x=>x.classList.toggle('active',x.dataset.tri===m));
    const c=document.getElementById('hist-confirm');if(c)c.style.display='none';
    const ph=document.getElementById('hist-phead');
    if(ph){ph.style.display=m?'':'none';
      if(m)ph.textContent=m==='handoff'?'Hand off from a point — branches a NEW agent seeded with context through that turn':"Rewind to a point — restores this agent's conversation to the end of that turn";}
    renderTimeline();}
  function tlPick(n){const st=TL_STATE[FOCUS]||{};if(!TL_MODE||st.state==='busy'||st.state==='gated'||st.state==='empty')return;
    const N=tlHead();if(TL_MODE==='rewind'&&n===N)return;   /* the head row is not a rewind target (no-op) */
    tlConfirm(n,N);}
  /* the rewind / handoff confirms — the shared inline-confirm shell in its stacked form: message row ·
     option/caveat rows · action row. Rewind is DANGER-toned (it discards the turns after the point —
     irreversible) and carries the honest k-from-last addressing caveat; Handoff keeps the base confirm
     tone (purely additive — the source is untouched) and carries the #switch-driven handoff-report
     option + the fork's file-state note (own git worktree when the cwd is a repo, shared cwd otherwise). */
  function tlConfirm(n,N){const c=document.getElementById('hist-confirm');if(!c)return;
    const a=AG[FOCUS]||{name:'agent'};const st=TL_STATE[FOCUS]||{};const k=N-n;
    if(TL_MODE==='rewind'){
      c.className='tl-confirm tl-confirm--stack foot-confirm--danger';
      c.innerHTML='<div class="tlc-row"><span>Rewind '+esc(a.name)+' to the end of Turn '+n+'? The '+(k===1?'turn':k+' turns')+' after it '+(k===1?'is':'are')+' discarded.</span></div>'
        +'<div class="tlc-note">Addressed as '+k+' back from the latest recorded turn — dashboard-initiated turns only. Turns driven from a raw terminal are invisible to this record, so the real target can sit that many prompts off if this agent was driven outside the dashboard.</div>'
        +'<div class="tlc-row"></div>';
      const row=c.lastElementChild;
      const cancel=document.createElement('button');cancel.className='btn btn-sm ml-auto';cancel.textContent='Cancel';cancel.onclick=()=>{c.style.display='none';};row.appendChild(cancel);
      const go=document.createElement('button');go.className='btn-danger btn-sm';go.innerHTML='<i data-lucide="undo-2" class="w-3.5 h-3.5"></i>Rewind';
      go.onclick=()=>{c.style.display='none';TL_ANCHOR[FOCUS]=n;tlSetMode(null);
        toast('Rewound '+a.name+' to the end of Turn '+n+' — rolled back '+k+' prompt'+(k===1?'':'s'));};
      row.appendChild(go);}
    else{
      c.className='tl-confirm tl-confirm--stack';
      const repo=st.repo!==false;const cwd=st.cwd||'~/agent-dashboard';
      c.innerHTML='<div class="tlc-row"><span>Hand off a new agent seeded through Turn '+n+(n===N?' (the head)':'')+'?</span></div>'
        +'<div class="tlc-row tlc-opt"><span class="tlc-optlab">With handoff report</span><span class="tlc-optnote">files a short summary of the source&#8217;s recent work to the Library and hands it to the new agent</span></div>'
        +'<div class="tlc-note">File state: '+(repo
          ?'the fork gets its own git worktree — '+cwd+' is a git repo, so its file changes stay isolated from '+esc(a.name)+'&#8217;s.'
          :cwd+' isn&#8217;t a git repo, so the fork shares the folder with '+esc(a.name)+' — concurrent edits can collide.')+'</div>'
        +'<div class="tlc-row"></div>';
      const opt=c.querySelector('.tlc-opt');
      const sw=document.createElement('button');sw.setAttribute('data-comp','switch');sw.className='swh on';sw.title='On — a handoff report is generated and filed';
      sw.onclick=()=>{const on=sw.classList.toggle('on');sw.title=on?'On — a handoff report is generated and filed':'Off — plain context carry-over only';};
      opt.appendChild(sw);
      const row=c.lastElementChild;
      const cancel=document.createElement('button');cancel.className='btn btn-sm ml-auto';cancel.textContent='Cancel';cancel.onclick=()=>{c.style.display='none';};row.appendChild(cancel);
      const go=document.createElement('button');go.className='btn-main btn-sm';go.innerHTML='<i data-lucide="git-branch" class="w-3.5 h-3.5"></i>Hand off';
      go.onclick=()=>{const rep=sw.classList.contains('on');c.style.display='none';
        switchTab('mid','create');prefillFromFocus();
        toast('Handed off from Turn '+n+' → new agent (seeded from '+a.name+(rep?' + handoff report':'')+')');};
      row.appendChild(go);}
    c.style.display='flex';LU();}
  /* ===== Create-wizard + Retire handlers (scripted demos) ===== */
  const NAME_POOL=['kai','drew','rowan','vale','wren','sage','nova','ash','juno','remy','sol','bex','indi','koa'];
  function rosterNames(){return new Set([...document.querySelectorAll('#graph-grid .node .text-foreground.truncate')].map(e=>e.textContent.replace(/^\d+\s+/,'').trim()));}
  function randomizeName(input){if(!input)return;const used=rosterNames();const free=NAME_POOL.filter(n=>!used.has(n));const pool=free.length?free:NAME_POOL;
    const idx=(input.value.length+used.size)%pool.length;input.value=pool[idx];}   /* deterministic pick (no Math.random in this env) */
  function randomizeCreateName(btn){const root=document.getElementById('mid-create');randomizeName(root&&root.querySelector('input[placeholder="auto-generated if blank"]'));}
  function prefillFromFocus(){const a=AG[FOCUS];if(!a)return;const root=document.getElementById('mid-create');if(!root)return;
    const roleIn=root.querySelector('.combo-in');if(roleIn)roleIn.value=a.role;
    const nameIn=root.querySelector('input[placeholder="auto-generated if blank"]');if(nameIn){nameIn.value='';randomizeName(nameIn);}
    /* NU-7: the Handoff prefill carries the SOURCE agent's model as a CONCRETE value (the abstract "inherit
       ← parent" label is retired). The focused agent's model reads from the Details #model-current label,
       which repaintAgentPanel keeps true to the focused card (e.g. "opus 4.8" → model + version). */
    const mc=document.getElementById('model-current');const mm=((mc&&mc.textContent)||'').trim().split(/\s+/);
    const tabs=root.querySelector('.model-tabs');if(tabs&&tabs._set&&mm[0])tabs._set(mm[0],mm[1]);}
  function createAgent(){const root=document.getElementById('mid-create');if(!root)return;
    const role=(root.querySelector('.combo-in')||{}).value||'agent';
    const name=(root.querySelector('input[placeholder="auto-generated if blank"]')||{}).value||'new';
    const no=(root.querySelector('input[placeholder="02"]')||{}).value||'02';
    toast('Created '+role+' · '+no+' '+name);switchTab('mid','details');}
  function resetCreate(){const root=document.getElementById('mid-create');if(!root)return;
    root.querySelectorAll('input').forEach(i=>{if(i.placeholder!=='02')i.value='';});
    const desc=root.querySelector('textarea');if(desc){desc.value='';if(desc.classList.contains('autosize'))autosize(desc);}
    root.querySelectorAll('[data-msel]').forEach(m=>{m._sel=new Set();buildMsel(m);});toast('Create form reset');}
  function cancelCreate(){switchTab('mid','details');}
  /* Shared inline confirm for the Details footer (Retire + R-batch item 11 Delete). Hides the WHOLE button row
     (so the confirm reads cleanly next to a two-button footer) and restores it on cancel/confirm. */
  function footConfirm(opts){const foot=document.getElementById('mid-foot-details');if(!foot)return;
    if(foot.querySelector('.foot-confirm'))return;
    const btns=[...foot.querySelectorAll('button')];btns.forEach(b=>b.style.display='none');
    const restore=()=>{c.remove();btns.forEach(b=>b.style.display='');};
    const c=document.createElement('div');c.className='tl-confirm foot-confirm'+(opts.danger?' foot-confirm--danger':'');c.setAttribute('data-comp','inline-confirm');c.style.display='flex';c.style.width='100%';c.style.alignItems='center';c.style.gap='var(--space-8)';
    c.innerHTML='<span>'+opts.msg+'</span>';
    const cancel=document.createElement('button');cancel.className='btn btn-sm ml-auto';cancel.textContent='Cancel';cancel.onclick=restore;
    const go=document.createElement('button');go.className=opts.goClass+' btn-sm';go.innerHTML=opts.goLabel;go.onclick=()=>{restore();opts.onGo();};
    c.appendChild(cancel);c.appendChild(go);foot.appendChild(c);LU();}
  /* ND 13: "Save" — the first Details action: writes the focused agent's CURRENT config out as an agent.md,
     with a filename input and a destination pick per the two-scope model — Save to project
     (<project>/.awl-cc-dash/agents) / Save to system (the persistent cross-project store, ~/.claude/agents).
     Reuses the inline footer-confirm pattern (scripted demo — the real write is backend work). */
  function saveAgentMd(btn){const a=AG[FOCUS]||{name:'agent',role:'agent'};const foot=document.getElementById('mid-foot-details');if(!foot||foot.querySelector('.foot-confirm'))return;
    const btns=[...foot.querySelectorAll(':scope > button')];btns.forEach(b=>b.style.display='none');
    const c=document.createElement('div');c.className='tl-confirm foot-confirm';c.setAttribute('data-comp','inline-confirm');
    c.style.cssText='display:flex;width:100%;align-items:center;gap:var(--space-6);flex-wrap:wrap;';
    c.innerHTML='<span style="flex:0 0 auto">Save config as</span>';
    const inp=document.createElement('input');inp.className='in';inp.style.cssText='flex:1 1 90px;min-width:70px;height:var(--size-24);padding:0 var(--space-6);';inp.value=(a.role||'agent')+'.md';c.appendChild(inp);
    const restore=()=>{c.remove();btns.forEach(b=>b.style.display='');};
    const mk=(cls,label,dest)=>{const b=document.createElement('button');b.className=cls+' btn-sm';b.textContent=label;
      b.onclick=()=>{const nm=(inp.value.trim()||'agent.md');restore();toast('Saved '+nm+' → '+dest);};return b;};
    c.appendChild(mk('btn-main','Save to project','<project>/.awl-cc-dash/agents/'));
    c.appendChild(mk('btn','Save to system','the system store (~/.claude/agents)'));
    const cancel=document.createElement('button');cancel.className='btn btn-sm';cancel.textContent='Cancel';cancel.onclick=restore;c.appendChild(cancel);
    foot.appendChild(c);inp.focus();inp.select();LU();}
  function retireAgent(btn){const a=AG[FOCUS]||{name:'this agent',role:''};
    footConfirm({msg:'Retire '+a.role+' · '+a.name+'? This ends the session.',goClass:'btn-danger',goLabel:'<i data-lucide="power" class="w-3.5 h-3.5"></i>Retire',
      onGo:()=>{toast('Retired '+a.name);const node=document.querySelector('#graph-grid .node[data-agent$="-'+FOCUS+'"]');if(node){node.style.opacity='.4';node.style.filter='grayscale(1)';}}});}
  /* R-batch item 11: permanently delete the focused agent — wipes its config + transcripts and removes it from the
     roster/graph (and would drop any links). Irreversible, so it's gated behind the same inline confirm, worded as
     "can't be undone" and confirmed with the solid-red Delete button. */
  function deleteAgent(btn){const a=AG[FOCUS]||{name:'this agent',role:''};
    footConfirm({danger:true,msg:'Permanently delete '+a.role+' · '+a.name+'? This wipes its configuration and transcripts and removes it from the roster, graph, and any links — this can\'t be undone.',
      goClass:'btn-danger-solid',goLabel:'<i data-lucide="trash-2" class="w-3.5 h-3.5"></i>Delete',
      onGo:()=>{toast('Deleted '+a.name+' — configuration + transcripts wiped');const node=document.querySelector('#graph-grid .node[data-agent$="-'+FOCUS+'"]');if(node)node.remove();}});}
  /* v9p3 kept: both tabs toggle off — but the LIST is a standing log now, visible unarmed (arming only
     makes rows click targets). The initial render rides boot() → selectNode → repaintAgentPanel →
     tlSetMode(null) — deliberately NOT here at parse time (the AG roster const is later in the file). */
  (function(){document.querySelectorAll('#hist-tabs .tri-tab').forEach(t=>t.onclick=()=>{
      const st=TL_STATE[FOCUS]||{};if(st.state==='gated')return;   /* belt + braces — the gated switcher is already CSS-inert */
      tlSetMode(t.classList.contains('active')?null:t.dataset.tri);});})();

  /* ===== RESPONSE / FORMAT grouped multi-select ===== */
  /* v10p10 (Next-up #2): Response popover reworked into graded axes (segmented = ordered single-select,
     toggle-grid = independent multi-select) split into STYLE (how it reads) vs BEHAVIOR (how it works),
     plus a Pace dial independent of the agent's Effort tier and a Reasoning-shown axis. Each axis holds a
     value; sel = live, def = default. The badge counts OVERRIDES (axes changed from default), not raw picks. */
  const FMT_ICON_TYPE='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>';
  const FMT_ICON_GAUGE='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14l4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/></svg>';
  const FMT_DATA={fmt:[
    {name:'Style',sub:'how it reads',icon:FMT_ICON_TYPE,groups:[
      {nm:'Length',   kind:'seg', opts:['Terse','Brief','Standard','Detailed','Exhaustive'], def:'Standard', sel:'Standard'},
      {nm:'Altitude', kind:'seg', opts:['High-level','Balanced','Low-level'],                def:'Balanced', sel:'Balanced'},
      {nm:'Register', kind:'seg', opts:['Technical','Mixed','Plain'],                        def:'Mixed',    sel:'Mixed'},
      {nm:'Structure',kind:'grid',cols:3,opts:['TL;DR','Numbered','Bullets','Tables','Prose'],def:['Bullets'],sel:['Bullets']},
      {nm:'Emphasis', kind:'grid',cols:2,opts:['Lead with answer','Cite sources','Skip hedging','Surface assumptions','Give tradeoffs'],def:[],sel:[]}
    ]},
    {name:'Behavior',sub:'how it works',icon:FMT_ICON_GAUGE,groups:[
      {nm:'Pace',kind:'seg',opts:['Snap','Quick','Standard','Careful','Deep'],def:'Standard',sel:'Standard',
        note:'<b>Independent of the agent’s Effort tier.</b> Effort = how much the model can think; Pace = how hard to work on this reply (verify, iterate, weigh options) before answering.'},
      {nm:'Reasoning shown',kind:'seg',opts:['Hidden','Key steps','Full'],def:'Hidden',sel:'Hidden'}
    ]}
  ]};
  const fmtGroups=id=>FMT_DATA[id].reduce((a,s)=>a.concat(s.groups),[]);
  const fmtOver=g=>g.kind==='seg'?g.sel!==g.def:JSON.stringify([...g.sel].sort())!==JSON.stringify([...g.def].sort());
  function countFmt(id){return fmtGroups(id).filter(fmtOver).length;}
  function fmtGroupHTML(id,si,gi,g){
    let body;
    if(g.kind==='seg'){
      body='<div data-comp="segmented-control" class="seg">'+g.opts.map(o=>'<button class="'+(g.sel===o?'active':'')+'" onclick="pickFmtSeg(\''+id+'\','+si+','+gi+',this)" data-o="'+o+'">'+o+'</button>').join('')+'</div>';
    }else{
      body='<div class="fmt-grid c'+(g.cols||2)+'">'+g.opts.map(o=>'<button class="tog-cell'+(g.sel.indexOf(o)>=0?' on':'')+'" onclick="toggleFmtCell(\''+id+'\','+si+','+gi+',this)" data-o="'+o+'">'+o+'</button>').join('')+'</div>';
    }
    return '<div class="fmt-group"><div class="fmt-gh"><span class="nm">'+g.nm+'</span><span class="mode">'+(g.kind==='seg'?'pick one':'multi')+'</span></div>'+body+(g.note?'<div class="fmt-note">'+g.note+'</div>':'')+'</div>';
  }
  function renderFmtMenu(id){const menu=document.getElementById(id+'-menu');if(!menu)return;
    menu.innerHTML=FMT_DATA[id].map((s,si)=>'<div class="fmt-section"><div class="fmt-sh">'+s.icon+'<span class="lbl">'+s.name+'</span><span class="sub">'+s.sub+'</span></div>'+s.groups.map((g,gi)=>fmtGroupHTML(id,si,gi,g)).join('')+'</div>').join('')
      +'<div class="fmt-foot"><span class="fmt-count">'+countFmt(id)+' changed from default</span><button class="fmt-reset" onclick="clearFmt(\''+id+'\')">Reset</button></div>';}
  function pickFmtSeg(id,si,gi,el){FMT_DATA[id][si].groups[gi].sel=el.dataset.o;renderFmtMenu(id);updateFmt(id);}
  function toggleFmtCell(id,si,gi,el){const g=FMT_DATA[id][si].groups[gi],o=el.dataset.o,i=g.sel.indexOf(o);if(i>=0)g.sel.splice(i,1);else g.sel.push(o);renderFmtMenu(id);updateFmt(id);}
  function clearFmt(id){FMT_DATA[id].forEach(s=>s.groups.forEach(g=>g.sel=g.kind==='seg'?g.def:[...g.def]));renderFmtMenu(id);updateFmt(id);}
  function updateFmt(id){const n=countFmt(id),btn=document.getElementById(id+'-btn');if(btn)btn.classList.toggle('active',n>0);const b=document.getElementById(id+'-badge');if(b)b.textContent=n;}
  /* v10p10: the reworked popover is taller than the old pill menu and the Prompt panel (.pcard-body / .rz-panel)
     clips overflow, so cap the menu height to the space available above the trigger (it opens upward) and let it
     scroll internally. Keeps every axis reachable at any panel height in this resizable layout. */
  function fitFmtMenu(id){const wrap=document.getElementById(id),menu=document.getElementById(id+'-menu');if(!wrap||!menu)return;
    const tr=wrap.getBoundingClientRect();let clip=wrap.parentElement;
    while(clip){const cs=getComputedStyle(clip);if(cs.overflowY==='hidden'||cs.overflowY==='auto'||cs.overflow==='hidden')break;clip=clip.parentElement;}
    const topBound=clip?clip.getBoundingClientRect().top:0;
    const avail=Math.max(120,Math.round(tr.top-topBound-12));   /* upward space above the trigger, minus a small gap */
    menu.style.maxHeight=avail+'px';menu.style.overflowY='auto';}
  function toggleFmt(id){const menu=document.getElementById(id+'-menu');if(!menu)return;const open=menu.classList.contains('open');closeAllPopups();if(!open){renderFmtMenu(id);menu.classList.add('open');fitFmtMenu(id);}}

  /* ===== team-graph directed edges ===== */
  /* planned (shipped, draws nothing): LINKS + drawEdges() render link edges, but there is no #edge-layer element so drawEdges() bails early — the host #graph-wrap is marked data-status="planned". */
  const LINKS=[['node-1','node-2',false],['node-1','node-3',false],['node-2','node-4',false],['node-3','node-7',true],['node-4','node-10',false],['node-5','node-1',false]];
  function drawEdges(){const layer=document.getElementById('edge-layer'),wrap=document.getElementById('graph-wrap');if(!layer||!wrap)return;
    const wr=wrap.getBoundingClientRect(),W=wrap.scrollWidth,H=wrap.scrollHeight;layer.setAttribute('width',W);layer.setAttribute('height',H);layer.style.width=W+'px';layer.style.height=H+'px';
    const defs=layer.querySelector('defs');layer.innerHTML='';if(defs)layer.appendChild(defs);const NS='http://www.w3.org/2000/svg';
    LINKS.forEach(L=>{const ea=document.getElementById(L[0]),eb=document.getElementById(L[1]);if(!ea||!eb)return;const ra=ea.getBoundingClientRect(),rb=eb.getBoundingClientRect();
      const ax=ra.left+ra.width/2-wr.left,ay=ra.top+ra.height/2-wr.top,bx=rb.left+rb.width/2-wr.left,by=rb.top+rb.height/2-wr.top;
      const dx=bx-ax,dy=by-ay,len=Math.hypot(dx,dy)||1,ux=dx/len,uy=dy/len,pa=Math.min(ra.width,ra.height)/2-2,pb=Math.min(rb.width,rb.height)/2+4;
      const ln=document.createElementNS(NS,'line');ln.setAttribute('x1',ax+ux*pa);ln.setAttribute('y1',ay+uy*pa);ln.setAttribute('x2',bx-ux*pb);ln.setAttribute('y2',by-uy*pb);
      ln.setAttribute('stroke','var(--muted)');ln.setAttribute('stroke-width','2.5');ln.setAttribute('stroke-dasharray','6 4');ln.setAttribute('marker-end','url(#arrow)');if(L[2])ln.setAttribute('marker-start','url(#arrow)');layer.appendChild(ln);});}
  function drawEdgesSoon(){requestAnimationFrame(()=>requestAnimationFrame(drawEdges));}

  /* ===== resizable handles (mirrors react-resizable-panels behaviour) ===== */
  function initResizers(){document.querySelectorAll('.rz-handle').forEach(h=>{h.addEventListener('mousedown',e=>{e.preventDefault();
    const horiz=h.dataset.orient==='h',prev=h.previousElementSibling,next=h.nextElementSibling;if(!prev||!next)return;
    const s=horiz?e.clientX:e.clientY,pS=horiz?prev.offsetWidth:prev.offsetHeight,nS=horiz?next.offsetWidth:next.offsetHeight;
    h.classList.add('dragging');   /* Next-up item 2: hold the teal drag state for the whole drag — :hover alone flashes back when a fast drag outruns the strip */
    document.body.style.cursor=horiz?'col-resize':'row-resize';document.body.style.userSelect='none';
    const ro=document.getElementById('rz-readout');   /* #15: cursor-following panel-size readout (px), shown only while dragging */
    const showReadout=e2=>{if(!ro)return;
      /* read the ACTUAL rendered sizes after the flex is applied (flex-grow means the clamped basis ≠ on-screen px) */
      const pPx=horiz?prev.offsetWidth:prev.offsetHeight,nPx=horiz?next.offsetWidth:next.offsetHeight;
      ro.innerHTML=Math.round(pPx)+'px<span class="rz-ro-sep">'+(horiz?'│':'─')+'</span>'+Math.round(nPx)+'px';   /* left/top panel first, then right/bottom */
      ro.classList.add('show');
      /* follow the cursor with a small offset, clamped to stay on-screen */
      const ow=ro.offsetWidth,oh=ro.offsetHeight,pad=6;
      let x=e2.clientX+14,y=e2.clientY+16;
      if(x+ow+pad>window.innerWidth)x=e2.clientX-ow-14;
      if(y+oh+pad>window.innerHeight)y=e2.clientY-oh-16;
      ro.style.left=Math.max(pad,x)+'px';ro.style.top=Math.max(pad,y)+'px';};
    const mv=e2=>{const d=(horiz?e2.clientX:e2.clientY)-s;const p=Math.max(150,pS+d),n=Math.max(150,nS-d);prev.style.flex=p+' 1 0';next.style.flex=n+' 1 0';drawEdges();showReadout(e2);};   /* v9p6 fix: flex-GROW proportions (basis 0, shrink 1) keep panels responsive after a drag — was '0 0 Npx' (fixed, no shrink), which made a dragged Team Graph refuse to shrink on later window resize and shoved the Prompts footer off-screen */
    showReadout(e);   /* #15: show immediately on mousedown so the readout appears before the first move */
    const up=()=>{document.removeEventListener('mousemove',mv);document.removeEventListener('mouseup',up);h.classList.remove('dragging');document.body.style.cursor='';document.body.style.userSelect='';if(ro)ro.classList.remove('show');autosizeAll();drawEdgesSoon();};
    document.addEventListener('mousemove',mv);document.addEventListener('mouseup',up);});});}

  /* ===== v8p6: per-agent thinking toggle (inline with Mode) ===== */
  function toggleThink(b){b.classList.toggle('on');const on=b.classList.contains('on');const l=b.querySelector('.tt-lbl');if(l)l.textContent='Thinking Mode '+(on?'On':'Off');}
  function toggleFast(b){if(b.classList.contains('gated'))return;b.classList.toggle('on');const on=b.classList.contains('on');const l=b.querySelector('.tt-lbl');if(l)l.textContent='Opus Fast-Mode '+(on?'On':'Off');}   /* labeled toggle-button: the label reads its own Off/On state; Fast is gated to Opus (see gateFast) */

  /* ===== Launch permissions (Create) — pre-arm Bypass/Auto at create ===== */
  /* Arming reveals the segment in the CREATE mode ring; disarming hides it again (silently absent — the ring
     never shows a segment that would no-op) and falls back to Edit if the hidden segment was the active pick. */
  function armToggle(sw,which){const on=sw.classList.toggle('on');
    sw.title=(on?'Armed — ':'Un-armed — ')+(which==='bypass'?'Bypass':'Auto')+(on?' joins the mode ring at launch':' is absent from the mode ring');
    const seg=document.getElementById('create-mode-seg');if(!seg)return;
    const btn=seg.querySelector('button[data-mode="'+which+'"]');if(!btn)return;
    btn.classList.toggle('seg-unarmed',!on);
    if(!on&&btn.classList.contains('active')){const fb=[...seg.querySelectorAll('button')].find(b=>b.textContent.trim()==='Edit');if(fb)segPick(fb);}}

  /* ===== v8p6: graph status badge → jump to the relevant surface, scoped to the focused agent ===== */
  function statusJump(status,el){
    const key=el?agKeyFromNode(el.closest('.node')):FOCUS;const a=AG[key];
    if(status==='pending'||status==='error'){switchTab('feed','inbox');     /* needs your input (pending) / run failed (error) → that agent's Inbox card (R-batch item 1: Error routes here too, mirroring pending) */
      const card=key&&document.querySelector('#feed-inbox .fcard[data-agent="'+key+'"]');
      if(card){card.classList.add('open');card.classList.add('sel');card.scrollIntoView({block:'nearest',behavior:'smooth'});card.classList.remove('reply-flash');void card.offsetWidth;card.classList.add('reply-flash');setTimeout(()=>card.classList.remove('reply-flash'),1000);LU();if(typeof eaUpdate==='function')eaUpdate('feed');}}   /* v10p1 #15 + v1.x #2: expand + SELECT (light-teal fill) + flash the agent's card; re-gate the feed Output Export + link-dd now that an Inbox card is selected (R-batch items 6a/7 — switchTab gated while nothing was selected yet) */
    else if(status==='active'){switchTab('prompt','history');}              /* in-flight → see what's been sent */
    else{switchTab('prompt','compose');if(a&&!a.user)replyTo(a.name);}      /* idle → start a prompt, pre-targeted */
  }

  /* ===== v8p6: Compose mic (voice dictation, mock) ===== */
  function toggleMic(b){if(b.disabled)return;b.classList.toggle('rec');const on=b.classList.contains('rec');b.title=on?'Listening… click to stop':'Dictate (voice → text)';}
  /* L: per-editor mic enablement. Each .editor-mic ghost mic binds DIRECTLY to its own field via data-micfield;
     it enables only while that field exists, is editable (input/textarea/contenteditable like .compose-rich), and is
     VISIBLE (offsetParent!==null — a display:none doc textarea or a hidden Compose/Plans tab disables it), and must NOT
     steal focus (its mousedown preventDefaults) so the field keeps focus and dictation targets it. */
  function isEditable(el){if(!el)return false;const t=el.tagName;if(t==='INPUT'||t==='TEXTAREA')return !el.disabled&&!el.readOnly;return el.isContentEditable===true;}
  function syncEditorMic(m){const f=m.dataset.micfield?document.getElementById(m.dataset.micfield):null;const ok=!!f&&isEditable(f)&&f.offsetParent!==null;
    if(ok){m.disabled=false;m.title=m.classList.contains('rec')?'Listening… click to stop':'Dictate (voice → text)';}
    else{m.disabled=true;if(m.classList.contains('rec'))m.classList.remove('rec');m.title='Dictate (voice → text) — field unavailable';}}
  function syncEditorMics(){document.querySelectorAll('.editor-mic').forEach(syncEditorMic);}
  function initEditorMics(){
    document.addEventListener('focusin',syncEditorMics);
    document.addEventListener('focusout',()=>setTimeout(syncEditorMics,0));   /* let the next focus target settle (e.g. tabbing field→field) before re-evaluating */
    syncEditorMics();}

  /* ============================ A12 + A3 — ONE generic Jump-to-End pill for EVERY scroll region ============================ */
  /* Auto-attaches a top + bottom jump pill to each scroll region. Behaviour (Slack/Discord/terminal): a pill shows only
     when scrolled away from that edge, snaps to the very top/bottom on click, and hides at the edge. Native scrollbars
     still handle incremental movement. This SINGLE implementation serves both the feed-specific "Jump to Feed Ends"
     (A12) and the global "Jump-to-End Pill for all scrollable windows" (A3) — there is no second, competing control. */
  const JUMP_THRESHOLD=24;   /* px from an edge before the pill appears / hides */
  /* the scroll regions to equip (curated so tiny popovers/menus are skipped); a few share a class, so use a broad set */
  /* contenteditable (.compose-rich) is intentionally EXCLUDED — injecting a non-editable child would corrupt its text */
  const JUMP_SELECTOR=['#feed-transcript','#feed-scratch','#feed-log','#feed-inbox','#prompt-history',
    '.md','.con-feed','.con-cat-list','.asset-grid','.docnav','.set-body','.fb-list','.ol-list','.tl','.aglist-scroll'].join(',');   /* D: `.md` is the REAL Plans+Documents editor-body scroller (.doc-view-host>.doc-ed>.md); the old `.doc-view` selector matched NO element in the live markup */
  function jumpUpdate(el){const pills=el._jumpPills;if(!pills)return;
    const top=pills.querySelector('.jump-top'),bot=pills.querySelector('.jump-bottom');
    const canScroll=el.scrollHeight-el.clientHeight>4;
    const fromTop=el.scrollTop, fromBot=el.scrollHeight-el.clientHeight-el.scrollTop;
    top.classList.toggle('show', canScroll && fromTop>JUMP_THRESHOLD);
    bot.classList.toggle('show', canScroll && fromBot>JUMP_THRESHOLD);
    /* keep the pills pinned to the VISIBLE bottom-right corner of the region as it scrolls (they live inside the
       scroller, so offset them by scrollTop). Right edge tracks the content box, inset from any scrollbar. */
    if(el._jumpOuter)return;   /* D: outer overlay (e.g. .compose-rich contenteditable): pills are CSS-pinned, never offset by scrollTop */
    pills.style.top=(el.scrollTop+el.clientHeight-pills.offsetHeight-10)+'px';
    pills.style.left=(el.scrollLeft+el.clientWidth-pills.offsetWidth-10)+'px';}
  function attachJump(el,mount){
    if(el._jumpPills)return;   /* idempotent */
    /* the scroll region itself is the positioning context (it has scroll, so it establishes a containing block for
       absolutely-positioned descendants once it isn't static).
       D: `mount` lets the pills live OUTSIDE the scroller (contenteditable .compose-rich case, where injecting a child
       node would corrupt its text) — they then mount into `mount` (an outer wrapper) and are CSS-pinned, not offset by scrollTop. */
    const host=mount||el;
    if(mount)el._jumpOuter=true;   /* flag: jumpUpdate must NOT reposition via scrollTop math; CSS pins them */
    const cs=getComputedStyle(host);if(cs.position==='static')host.style.position='relative';
    const pills=document.createElement('div');pills.className='jump-pills'+(mount?' jump-pills--outer':'');
    pills.innerHTML='<button class="jump-pill jump-top" title="Jump to top" type="button"><i data-lucide="chevrons-up"></i></button>'
      +'<button data-comp="jump-to-end-pill" class="jump-pill jump-bottom" title="Jump to bottom" type="button"><i data-lucide="chevrons-down"></i></button>';
    host.appendChild(pills);
    el._jumpPills=pills;
    pills.querySelector('.jump-top').addEventListener('click',()=>el.scrollTo({top:0,behavior:'smooth'}));
    pills.querySelector('.jump-bottom').addEventListener('click',()=>el.scrollTo({top:el.scrollHeight,behavior:'smooth'}));
    let raf=0;el.addEventListener('scroll',()=>{if(raf)return;raf=requestAnimationFrame(()=>{raf=0;jumpUpdate(el);});},{passive:true});
    if(window.ResizeObserver){new ResizeObserver(()=>jumpUpdate(el)).observe(el);}
    jumpUpdate(el);}
  function initJumpPills(){document.querySelectorAll(JUMP_SELECTOR).forEach(el=>attachJump(el));   /* D: wrap so forEach's index arg never leaks into attachJump's `mount` param */
    /* D: the contenteditable compose field is NOT in JUMP_SELECTOR (a child node would corrupt its text) — attach its
       pill via an OUTER wrapper instead, so the overlay lives outside .compose-rich. */
    const cf=document.getElementById('compose-field');if(cf&&cf.parentElement&&cf.parentElement.classList.contains('compose-jump-wrap'))attachJump(cf,cf.parentElement);
    LU();
    /* re-evaluate every region's pills on window resize (content/region size may change which edges are reachable) */
    window.addEventListener('resize',()=>document.querySelectorAll(JUMP_SELECTOR).forEach(el=>{if(el._jumpPills)jumpUpdate(el);}));
    window.addEventListener('resize',()=>{const c=document.getElementById('compose-field');if(c&&c._jumpPills)jumpUpdate(c);});}   /* D: re-evaluate the compose overlay on resize too */
  /* a tab/content switch can change which region is scrollable or its content height — recheck all pills */
  function refreshJumpPills(){document.querySelectorAll(JUMP_SELECTOR).forEach(el=>{if(el._jumpPills)jumpUpdate(el);else attachJump(el);});
    const cf=document.getElementById('compose-field');if(cf){if(cf._jumpPills)jumpUpdate(cf);else if(cf.parentElement&&cf.parentElement.classList.contains('compose-jump-wrap'))attachJump(cf,cf.parentElement);}
    LU();}
  /* v1.2: attach an asset to the prompt — opens the Library → Assets picker; a newly attached image
     also registers in the Assets grid (Assets stays the single source of truth). Wired in the real build (mock). */
  function composeAttach(b){switchTab('doc','assets');toast('Pick an asset to attach — Library → Assets (the single source of truth for media)');}
  /* ===== Prompts Send / Revise (scripted demos) ===== */
  function sendPrompt(){const tgt=[...document.querySelectorAll('#prompt-targets .agrow.on')].map(r=>(r.querySelector('.ag-name')||{}).textContent).filter(Boolean);
    if(!tgt.length){toast('Pick at least one target (To)');return;}
    const timing=((document.querySelector('#prompt-actions .split--primary .split-lbl')||{}).textContent||'Now').trim();
    toast('Sent ('+timing+') to '+tgt.join(', '));}
  function reviseDraft(){const scope=((document.querySelector('#revise-split .split-lbl')||{}).textContent||'Grammar').trim();toast('Revising draft ('+scope+')…');}
  /* ===== Link Config Save / Delete (scripted demos) ===== */
  function bumpLinks(d){const el=document.getElementById('foot-links');if(el){el.textContent=Math.max(0,(parseInt(el.textContent,10)||0)+d);}}
  function linkSave(){const dir=((document.getElementById('link-dir')||{}).title||'A ↔ B (both)');   /* Next-up item 3: the fallback mirrors the cycler's new A↔B default */
    const trig=(((document.querySelector('#link-drawer .trig-dd .split-mi.sel b')||{}).textContent)||'Queue').trim();   /* Next-up item 17: Trigger is a dropdown now (.split-mi menu items), not a seg */
    const rel=((document.querySelector('#link-drawer .seg button[data-rel].active')||{}).textContent||'Direct messaging').trim();   /* ONE relationship per link — read the single-select segment */
    toast('Link saved — '+dir+' · '+trig+' · '+rel);toggleDrawer();bumpLinks(1);}
  function linkDelete(){toast('Link removed');toggleDrawer();bumpLinks(-1);}

  /* ===== v8p6 → ND 12 → 2026-07-17: Role combobox — the agent.md PRESET LOADER. Its entries group by the settled
     two-scope model: SYSTEM (the persistent cross-project store, incl. ~/.claude/agents — the old "User" scope
     folded in) and PROJECT (<project>/.awl-cc-dash/agents). Picking an entry in Create auto-fills the Create
     fields from the file's front matter (prefillFromRole) INCLUDING color — a `color:` front-matter key (the
     named-color convention: orange · green · cyan · purple · pink …) maps onto the agent palette and sets the
     Create color swatch; icon is NEVER prefilled (it differentiates same-role agents — always hand-chosen at
     Create). In Details the ENTIRE tab is view-only (2026-07-17 — widens the original ND 12 Role-only lock):
     identity + config are set at Create and lock once the session exists (config is create/launch-time —
     ARCHITECTURE §7.15), so every pencil is gone, not just Role's. ===== */
  const ROLE_DEFS=[
    {group:'System agents (~/.claude/agents · cross-project)',items:[
      {name:'gsd-debugger',desc:'Investigates bugs using the scientific method; manages debug sessions and checkpoints.',skills:[],tools:['Read','Write','Edit','Bash','Grep','Glob','WebSearch'],color:'orange'},
      {name:'gsd-planner',desc:'Creates executable phase plans with task breakdown and dependency analysis.',skills:[],tools:['Read','Grep','Glob','Bash'],color:'green'},
      {name:'gsd-codebase-mapper',desc:'Explores a codebase and writes structured analysis docs (STACK, ARCHITECTURE, …).',skills:[],tools:['Read','Grep','Glob','Bash'],color:'cyan'},
      {name:'gsd-ui-researcher',desc:'Produces UI-SPEC.md design contracts for frontend phases.',skills:[],tools:['Read','Grep','Glob','WebSearch','WebFetch']},   /* no color: key in its front matter (a hex there, actually) — demos the color-less prefill path */
    ]},
    {group:'Project agents (<project>/.awl-cc-dash/agents)',items:[
      {name:'echo',desc:'Session distiller and intent archaeologist. Extracts structured implementation briefs from messy, multi-turn Claude Code sessions.',skills:['distill','session-brief'],tools:['Read','Glob','Grep','Bash','WebSearch','WebFetch'],color:'purple'},
      {name:'vibe-guide',desc:'Builds applications through conversation — turns user vision, references and vibes into working apps while handling the technical complexity.',skills:['ui-ux-pro-max:ui-styling','ui-ux-pro-max:design-system'],tools:['Read','Glob','Grep','Bash','Write','Edit','WebSearch','WebFetch'],color:'pink'},
    ]},
  ];
  /* front-matter named colors (Claude Code's subagent color: set) → the nearest existing --ag-* palette token
     (names only — the swatch grid already carries the var(--ag-*) values; no new color values are minted here) */
  const AG_FROM_NAMED={red:'vermilion',orange:'amber',yellow:'citron',green:'emerald',cyan:'cyan',blue:'cobalt',purple:'violet',pink:'magenta'}; /* mirrors sidecar/roles.py NAMED_COLOR_TO_HEX — the product authority for named→token mapping */
  function buildCombo(el){const pop=el.querySelector('.combo-pop');if(!pop)return;
    pop.innerHTML=ROLE_DEFS.map(g=>'<div class="combo-gh">'+g.group+'</div>'+g.items.map(it=>'<button type="button" class="combo-opt" onclick="pickCombo(event,this)" data-name="'+it.name+'"><b>'+it.name+'</b><span class="sub">'+it.desc+'</span></button>').join('')).join('');}
  function toggleCombo(btn){const el=btn.closest('.combo');const pop=el.querySelector('.combo-pop');const open=pop.classList.contains('open');closeAllPopups();if(!open){buildCombo(el);pop.classList.add('open');}}
  function pickCombo(e,btn){e.stopPropagation();const el=btn.closest('.combo');const name=btn.dataset.name;const inp=el.querySelector('.combo-in');if(inp)inp.value=name;el.querySelector('.combo-pop').classList.remove('open');if(el.hasAttribute('data-create'))prefillFromRole(name);}
  function prefillFromRole(name){const def=ROLE_DEFS.flatMap(g=>g.items).find(d=>d.name===name);if(!def)return;const root=document.getElementById('mid-create');if(!root)return;
    const desc=root.querySelector('textarea');if(desc){desc.value=def.desc;if(desc.classList.contains('autosize'))autosize(desc);}
    const sk=root.querySelector('[data-msel="skills"]');if(sk){sk._sel=new Set(def.skills);buildMsel(sk);}
    const tl=root.querySelector('[data-msel="tools"]');if(tl){tl._sel=new Set(def.tools);buildMsel(tl);}
    /* 2026-07-17: color prefills too — a color: front-matter key maps (AG_FROM_NAMED) onto the palette and picks
       the matching swatch via pickColor (the picker's own state-setter, so swatch + name + --cur-color all move);
       no color: key → the current pick stands. Icon is deliberately NOT prefilled — always hand-chosen. */
    if(def.color){const ag=AG_FROM_NAMED[def.color]||def.color;const sw=root.querySelector('[data-colorgrid] .sw[data-name="'+ag+'"]');if(sw)pickColor(sw);}}

  /* ===== v8p6: multi-select dropdowns (Skills from skills files · Tools = native Claude Code tools) ===== */
  const MSEL_CATALOG={
    skills:[
      {group:'User skills (~/.claude/skills)',items:['browser-use','defuddle','distill','learned','research-brief','session-brief','session-handoff','workspace-status']},
      {group:'Plugin skills',items:['security-review','tdd-workflow','deep-research','api-design','frontend-patterns','ui-ux-pro-max:ui-styling','ui-ux-pro-max:design-system']},
    ],
    tools:[
      {group:'Core tools',items:['Bash','Read','Write','Edit','Glob','Grep','WebSearch','WebFetch']},
      {group:'More native tools',items:['Agent','AskUserQuestion','NotebookEdit','TodoWrite','ExitPlanMode','Skill','SendMessage','LSP','EnterWorktree','ExitWorktree','BashOutput','KillShell','SlashCommand','PowerShell']},
    ],
    /* per-agent scoping — which MCP servers / plugins this agent may use, and the deny rules that hard-block it.
       MCP / plugins take effect at the agent's next launch/restart; deny is the reliable hard-block (allow-lists are ignored under bypass — a claude bug). */
    mcp:[
      {group:'Configured MCP servers — none = all available',items:['playwright','github','supabase','firecrawl','exa','notion','docker','brave-search','rentcast','attom-api']},
    ],
    plugins:[
      {group:'Installed plugins — none = all enabled',items:['claude-mem','superpowers','everything-claude-code','ui-ux-pro-max','pyright-lsp']},
    ],
    denyrules:[
      {group:'Deny rules — tools/commands this agent can never run',items:['Bash(rm -rf:*)','Bash(sudo:*)','Bash(git push:*)','Bash(curl:*)','Write(/etc/**)','Write(**/.env)','Read(**/.env)','Read(**/secrets/**)','WebFetch','Edit(**/*.lock)']},
    ],
  };
  function mselState(el){if(!el._sel){try{el._sel=new Set(JSON.parse(el.dataset.sel||'[]'));}catch(e){el._sel=new Set();}}return el._sel;}
  function buildMsel(el){const cat=MSEL_CATALOG[el.dataset.msel]||[];const sel=mselState(el);const box=el.querySelector('.msel-box');const pop=el.querySelector('.msel-pop');
    const chips=[...sel].map(it=>'<span class="msel-chip">'+it+'<button type="button" onclick="mselRemove(event,this)" data-it="'+it+'"><i data-lucide="x"></i></button></span>').join('');
    if(box)box.innerHTML=(chips||'<span class="msel-ph">Select…</span>')+'<i data-lucide="chevrons-up-down" class="msel-cv"></i>';
    if(pop)pop.innerHTML=cat.map(g=>'<div class="msel-gh">'+g.group+'</div>'+g.items.map(it=>'<button type="button" class="msel-opt'+(sel.has(it)?' on':'')+'" onclick="mselPick(event,this)" data-it="'+it+'"><i data-lucide="check" class="mck"></i><span class="mname">'+it+'</span></button>').join('')).join('');
    LU();}
  function toggleMsel(box){const el=box.closest('.msel');const pop=el.querySelector('.msel-pop');const open=pop.classList.contains('open');closeAllPopups();if(!open){buildMsel(el);pop.classList.add('open');}}
  function mselPick(e,btn){e.stopPropagation();const el=btn.closest('.msel');const sel=mselState(el);const it=btn.dataset.it;if(sel.has(it))sel.delete(it);else sel.add(it);buildMsel(el);el.querySelector('.msel-pop').classList.add('open');}
  function mselRemove(e,btn){e.stopPropagation();const el=btn.closest('.msel');mselState(el).delete(btn.dataset.it);buildMsel(el);}

  /* ===== Link Config (amended, next-up item 17) — Relationship single-select + Shared-context disclosure =====
     ONE relationship per link (wanting both = two links — supersedes the old "a link can be both" multi-toggle), so
     Relationship is a single-select segment (data-rel buttons in a .seg). Picking one re-defaults the Trigger
     dropdown to that relationship's natural delivery — Direct messaging → Queue · Shared context → Piggyback —
     while SC keeps the FULL trigger menu (no gating; an actively-delivered share just costs the target a turn to
     ingest, which is why Piggyback stays the SC default). The same handler still drives the nested content-type
     row's plain multi-toggles (no data-rel → plain toggle); the disclosure re-syncs on every call, scoped to the
     button's own drawer, so multiple instances stay independent (originally the mockup + the retired gallery's specimen). */
  function linkRel(btn){const wrap=btn.closest('.drawer');
    if(btn.dataset.rel){
      if(!btn.classList.contains('active')){
        const g=btn.closest('.seg');if(g)g.querySelectorAll('button').forEach(x=>x.classList.toggle('active',x===btn));
        if(wrap)linkTrigSet(wrap,btn.dataset.rel==='shared'?'Piggyback':'Queue');}}
    else btn.classList.toggle('on');
    if(!wrap)return;
    const sharedOn=!!wrap.querySelector('[data-rel="shared"].active');
    const block=wrap.querySelector('.link-shared');if(block)block.classList.toggle('hidden',!sharedOn);}
  /* set the Trigger dropdown's selection by name (the per-relationship default above) */
  function linkTrigSet(wrap,name){const dd=wrap.querySelector('.trig-dd');if(!dd)return;
    dd.querySelectorAll('.split-mi').forEach(x=>x.classList.toggle('sel',((x.querySelector('b')||{}).textContent||'').trim()===name));
    const l=dd.querySelector('.trig-lbl');if(l)l.textContent=name;}
  /* Trigger menu item pick — the Send timing-menu pattern, standalone (no .split ancestor, so pickSplit can't serve it) */
  function pickTrig(mi){const menu=mi.closest('.split-menu');menu.querySelectorAll('.split-mi').forEach(x=>x.classList.toggle('sel',x===mi));
    const dd=menu.closest('.trig-dd');const l=dd?dd.querySelector('.trig-lbl'):null;if(l)l.textContent=((mi.querySelector('b')||{}).textContent||'').trim();
    menu.classList.remove('open');}
  /* the backfill is the shared switch primitive (.swh) — a plain config toggle (no registry-enable toast) */
  function linkSwitch(el){el.classList.toggle('on');el.title=el.classList.contains('on')?'On — backfill all prior context once':'Off — incremental updates only';}

  /* ===== Link tracking list (amended, next-up item 17) — collapsible Active / Expired sections =====
     The list splits into Active Links / Expired Links accordion sections (the SECTION carries the state — expired
     rows get NO gray-out, per the Inbox typed-section precedent, and stay legible for the future master/detail
     "load + re-arm" extension). Within each section links group by agent: each link joins two agents, so it is
     DOUBLE-LISTED under both endpoints, entries sorted PEER-ADJACENT (same peer together, roster order); each entry
     shows a directional arrow relative to THIS group's agent (to · from · both — Lucide arrow-right / arrow-left /
     arrow-left-right, next-up item 18) + the OTHER agent + its FULL relationship label (a link now has exactly one).
     The group-header identity badge carries the corner-count overlay badge (teal >0; the muted zero state has no
     live instance here — zero-link groups don't render inside the split sections; its look is preserved in the
     archived gallery snapshot; declared as the corner-count-badge's `none` data-variants state by the 2026-07-05 sweep).
     LINKS_CFG is keyed by agent name (distinct from the planned on-graph `LINKS` edge data, which is node-id keyed);
     ONE relationship per link — wanting both = two links (see the sandy↔drew pair). */
  const LINKS_CFG=[
    {a:'sandy',b:'kai',dir:'ab',rel:'direct'},
    {a:'sandy',b:'drew',dir:'both',rel:'direct'},
    {a:'sandy',b:'drew',dir:'both',rel:'shared'},
    {a:'max',b:'kai',dir:'ba',rel:'shared'},
    {a:'vega',b:'sandy',dir:'both',rel:'direct'},
    /* expired examples — an End After limit reached, or manually ended */
    {a:'sandy',b:'max',dir:'ab',rel:'shared',expired:true},
    {a:'kai',b:'drew',dir:'both',rel:'direct',expired:true},
    {a:'vega',b:'wren',dir:'ba',rel:'shared',expired:true}
  ];
  function relLabel(rel){return rel==='direct'?'Direct messaging':'Shared context';}
  /* arrow relative to the group's agent (returns the Lucide icon name): isA = this group's agent is the link's `a` endpoint */
  function linkArrow(dir,isA){if(dir==='both')return 'arrow-left-right';const outgoing=(dir==='ab')===isA;return outgoing?'arrow-right':'arrow-left';}
  /* one section's per-agent groups from a [{lk,i}] slice (i = the LINKS_CFG index) */
  function linkGroupsHTML(list){let html='';AG_ORDER.forEach(key=>{
      const mine=list.filter(({lk})=>lk.a===key||lk.b===key);
      if(!mine.length||!AG[key])return;const a=AG[key];
      mine.sort((x,y)=>AG_ORDER.indexOf(x.lk.a===key?x.lk.b:x.lk.a)-AG_ORDER.indexOf(y.lk.a===key?y.lk.b:y.lk.a));   /* peer-adjacent */
      html+='<div data-comp="registry-group-header" class="reg-grp link-grp"><span class="ovl-host">'+badgeHTML(a)
        +'<span data-comp="corner-count-badge" data-variants="none" class="ovl-count" title="'+mine.length+' link'+(mine.length===1?'':'s')+'">'+mine.length+'</span></span></div>';
      html+=mine.map(({lk,i})=>{const isA=lk.a===key;const other=AG[isA?lk.b:lk.a];if(!other)return '';
        const arrow=linkArrow(lk.dir,isA);const ttl=arrow==='arrow-right'?'to':(arrow==='arrow-left'?'from':'both ways');
        return '<button class="link-row" onclick="linkListPick(this)" data-link="'+i+'" title="Load this link to edit (planned)">'
          +'<span class="link-arrow" title="'+ttl+'"><i data-lucide="'+arrow+'"></i></span>'+badgeHTML(other)
          +'<span class="link-rel">'+relLabel(lk.rel)+'</span></button>';}).join('');});
    return html;}
  function linkSecHTML(lab,items,open){return '<div class="link-sec'+(open?' open':'')+'"><button class="link-sec-head" type="button" onclick="toggleLinkSec(this)">'
    +'<i data-lucide="chevron-right" class="lchev"></i><span class="lbl">'+lab+'</span><span class="link-sec-n">'+items.length+'</span></button>'
    +'<div class="link-sec-body">'+(items.length?linkGroupsHTML(items):'<div class="link-empty">None.</div>')+'</div></div>';}
  function renderLinkList(){const el=document.getElementById('link-list');if(!el)return;
    const all=LINKS_CFG.map((lk,i)=>({lk,i}));
    if(!all.length){el.innerHTML='<div class="link-empty">No links yet — connect two agents from the Team panel to create one.</div>';return;}
    el.innerHTML=linkSecHTML('Active Links',all.filter(o=>!o.lk.expired),true)
      +linkSecHTML('Expired Links',all.filter(o=>o.lk.expired),false);
    LU();}
  /* sticky accordion fold — a toggle, not a popup (deliberately NOT in closeAllPopups) */
  function toggleLinkSec(btn){btn.closest('.link-sec').classList.toggle('open');}
  /* optional master/detail: clicking a list entry would load it into the fields above — planned (the drawer's
     Save/Delete are toast+counter only), so for now it just selects the row + acknowledges via toast. */
  function linkListPick(row){const el=row.closest('.link-list');if(el)el.querySelectorAll('.link-row.sel').forEach(r=>r.classList.remove('sel'));
    row.classList.add('sel');toast('Link loaded — edit the fields above (planned)');}

  /* ===== v8p7: Source dropdown (single-select, mirrors the old Source list) ===== */
  /* Next-up item 8: kept as a thin delegate — the Compose From selector is a .dd--acc accordion whose trigger
     now routes through toggleSrcPop(this) like every other selector; this survives for any stale caller. */
  function toggleSourceDD(){const dd=document.getElementById('source-dd');if(!dd)return;const t=dd.querySelector('.dd-trig');if(t)toggleSrcPop(t);}
  function pickSource(el){const dd=el.closest('.src-dd');if(!dd)return;dd.querySelectorAll('.agrow').forEach(r=>r.classList.remove('on'));el.classList.add('on');
    const trig=dd.querySelector('.dd-trig');const tile=el.querySelector('.agtile').cloneNode(true);const lab=el.querySelector('.ag-lab').cloneNode(true);
    trig.innerHTML='';trig.appendChild(tile);trig.appendChild(lab);const cv=document.createElement('i');
    const acc=dd.classList.contains('dd--acc');   /* Next-up item 8: accordion selectors carry the accordion chevron (right → down); popover ones keep chevrons-up-down */
    cv.setAttribute('data-lucide',acc?'chevron-right':'chevrons-up-down');cv.className=acc?'acc-cv':'picker-cv';trig.appendChild(cv);
    dd.querySelector('.src-pop').classList.remove('open');dd.classList.remove('open');LU();}

  /* ===== v8p7: History — selectable cards + footer action strip ===== */
  /* Next-up item 9: the History-tab From MULTI-SELECT FILTER (#hist-from — the To list minus Scratch, agents
     only). Agent-sourced prompts gate on the selection; the operator's own (from:user) prompts always show —
     User isn't a row here. Compose keeps its single-select From source untouched (multiple sources only make
     sense for filtering history, not for sending). */
  function applyHistFilters(){const fil=document.getElementById('hist-from'),list=document.getElementById('hist-list');if(!fil||!list)return;
    const on=new Set([...fil.querySelectorAll('.agrow.on')].map(r=>r.dataset.ag));
    [...list.querySelectorAll('.fcard')].forEach(c=>{const o=HIST[+c.dataset.hidx];if(!o)return;
      c.style.display=(o.from==='user'||on.has(o.from))?'':'none';});}
  /* (the old selectHistCard whole-card toggler was removed — the live select path is fcardSel(), which re-gates
     via eaUpdate('hist'); a separate setter that omitted that gate was a latent trap.) */
  function histAct(a){const sel=[...document.querySelectorAll('#hist-list .fcard.sel')];
    if(a==='edit'){switchTab('prompt','compose');return;}
    if(!sel.length){toast('Select a prompt first');return;}
    if(a==='copy'){if(navigator.clipboard){const txt=sel.map(c=>{const b=c.querySelector('.fcard-full');return b?b.textContent:'';}).join('\n\n');navigator.clipboard.writeText(txt).catch(()=>{});}toast('Copied '+sel.length+' prompt'+(sel.length>1?'s':''));return;}
    if(a==='retry'){toast('Retrying '+sel.length+' prompt'+(sel.length>1?'s':'')+'…');return;}
    if(a==='stop'){toast('Stopping '+sel.length+' run'+(sel.length>1?'s':''));sel.forEach(s=>{const db=s.querySelector('.dbadge');if(db){db.className='dbadge db-held';db.textContent='Held';}});}}
  /* Next-up item 5: delete a prompt BEFORE it runs — the danger trash ghost after Edit (only on cards whose
     status is not Active/Complete, i.e. Queued/Next/Held), routed through the standard inline confirm
     (.tl-confirm, danger-toned like the Delete-agent confirm) before the card + its HIST entry are removed. */
  function histDelete(btn){const card=btn.closest('.fcard');if(!card||card.querySelector('.hist-del-confirm'))return;
    const st=card.querySelector('.dbadge');const lab=st?st.textContent:'';
    const c=document.createElement('div');c.setAttribute('data-comp','inline-confirm');c.className='tl-confirm foot-confirm--danger hist-del-confirm';c.style.display='flex';
    c.innerHTML='<span>Delete this '+(lab?lab+' ':'')+'prompt? It hasn\'t run yet.</span>';
    const cancel=document.createElement('button');cancel.className='btn btn-sm ml-auto';cancel.textContent='Cancel';cancel.onclick=e=>{e.stopPropagation();c.remove();};
    const go=document.createElement('button');go.className='btn-danger-solid btn-sm';go.innerHTML='<i data-lucide="trash-2" class="w-3.5 h-3.5"></i>Delete';
    go.onclick=e=>{e.stopPropagation();const i=parseInt(card.dataset.hidx,10);
      if(!isNaN(i)&&HIST[i]){HIST.splice(i,1);const h=document.getElementById('hist-list');if(h){h.innerHTML=HIST.map(histCardHTML).join('');if(typeof applyHistFilters==='function')applyHistFilters();}}
      else card.remove();   /* a card with no HIST index (originally the retired gallery's specimen) — just drop it */
      toast('Deleted the '+(lab||'queued')+' prompt');eaUpdate('hist');LU();};
    c.appendChild(cancel);c.appendChild(go);
    const head=card.querySelector('.fcard-head');if(head)head.insertAdjacentElement('afterend',c);else card.appendChild(c);LU();}
  /* I3: select/deselect-all for History (parallel to feedSelectAll) */
  function histSelectAll(btn){const cards=[...document.querySelectorAll('#hist-list .fcard')].filter(c=>c.style.display!=='none');
    const allOn=cards.length&&cards.every(c=>c.classList.contains('sel'));cards.forEach(c=>c.classList.toggle('sel',!allOn));eaUpdate('hist');}
  /* I3: Output Export for History (parallel to feedExport) */
  function histExport(mode){closeAllPopups();const root=document.getElementById('hist-list');if(!root)return;
    const cards=[...root.querySelectorAll('.fcard.sel')];   /* selection-only */
    if(!cards.length){toast('Select prompts first');return;}
    const txt=cards.map(c=>{const b=c.querySelector('.fcard-full');return b?b.textContent.trim():'';}).filter(Boolean).join('\n\n');
    if(mode==='copy-sel'){if(navigator.clipboard)navigator.clipboard.writeText(txt).catch(()=>{});toast('Copied '+cards.length+' prompt'+(cards.length>1?'s':''));return;}
    if(mode==='file-sel'){const n=cards.length;const fname='history-export-'+(new Date().toTimeString().slice(0,5).replace(':',''))+'.md';addDocPaste(txt,fname);   /* R-batch item 8: route to Library → Documents + the Add-document (Paste) workflow */
      toast('Exported '+n+' prompt'+(n>1?'s':'')+' → Documents · '+fname);}}

  /* ===== v8p8: Messages — multi-select cards + footer actions ===== */
  /* (the old selectMsgCard toggler was removed — the live select paths are txWholeSel()/txBlkSelMulti(), which
     re-gate via eaUpdate('feed'); a separate setter that omitted that gate was a latent trap.) */
  function txAct(a){const sel=[...document.querySelectorAll('#feed-transcript .rcard.sel')];
    if(a==='copy'&&sel.length&&navigator.clipboard){const txt=sel.map(c=>{const b=c.querySelector('.rc-body');return b?b.textContent:'';}).join('\n\n');navigator.clipboard.writeText(txt).catch(()=>{});return;}
    if(a==='stop'){toast('Stopping the active run…');return;}   /* v1.x #6: Stop the agent's run (mock) */
    /* summarize / share — wired to the runtime in the real build (mock here) */}

  /* ===== v9p4: Settings (step-into full-window view) ===== */
  function openSettings(tab){
    const v=document.getElementById('settings-view');if(!v)return;
    v.classList.add('open');v.setAttribute('aria-hidden','false');
    const g=document.getElementById('settings-gear');if(g)g.classList.add('on');
    if(typeof tab==='string'&&tab)settingsTab(tab);
    LU();
  }
  function closeSettings(){
    const v=document.getElementById('settings-view');if(!v)return;
    v.classList.remove('open');v.setAttribute('aria-hidden','true');
    setGlobalConfirm(false);
    const g=document.getElementById('settings-gear');if(g)g.classList.remove('on');
  }
  function settingsTab(t){
    document.querySelectorAll('.set-pane').forEach(p=>p.classList.remove('active'));
    const pane=document.getElementById('set-'+t);if(pane)pane.classList.add('active');
    document.querySelectorAll('[data-set-tab]').forEach(b=>b.classList.toggle('active',b.dataset.setTab===t));
    setGlobalConfirm(false);
    /* Settings intentionally does NOT persist its tab — it always opens on its default lead tab (Projects). */
    LU();
  }
  function setScope(grp,sc,btn){
    document.querySelectorAll('[data-scopepane="'+grp+'"]').forEach(p=>p.classList.remove('active'));
    const el=document.getElementById(grp+'-'+sc);if(el)el.classList.add('active');
    const seg=btn.closest('.set-scope');if(seg)seg.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b===btn));
    if(grp==='config')setGlobalConfirm(false);
    LU();
  }
  function setSwitch(el){if(el.classList.contains('sw-locked')){toast('Blocked — resolve the connection/OAuth issue first');return;}
    el.classList.toggle('on');const on=el.classList.contains('on');el.title=on?'Enabled':'Disabled';
    const row=el.closest('.reg-row');const nm=row?((row.querySelector('.reg-nm,.reg-name,b')||{}).textContent||'').trim():'';
    toast((on?'Enabled ':'Disabled ')+(nm||'server')+(on?'':' — parked'));}   /* MCP / plugin enable-disable (scripted demo) */
  function pickPlain(btn){const g=btn.closest('.set-scope');if(g)g.querySelectorAll('button').forEach(b=>b.classList.toggle('active',b===btn));}
  function setGlobalConfirm(show){const c=document.getElementById('config-confirm');if(c)c.classList.toggle('show',!!show);}
  function askGlobalEdit(){setGlobalConfirm(true);const c=document.getElementById('config-confirm');if(c)c.scrollIntoView({block:'nearest',behavior:'smooth'});}

  /* ===== Projects (Settings → Projects tab) — open/close/register + the one-at-a-time rule =====
     The tab itself switches through the shared settingsTab() mechanism (data-set-tab="projects" → #set-projects);
     this block wires the pane's own behavior. Guarded on #proj-list so it no-ops on any page without the Projects pane. */
  const PROJ = [
    { name:'awl-cc-dash',         path:'~/MeDocuments/AppData/Anthropic/awl-cc-dash',         agents:13, running:true,  last:'2026-07-01 18:42' },
    { name:'claude-code-sandbox', path:'~/MeDocuments/AppData/Anthropic/claude-code-sandbox', agents:6,  running:false, last:'2026-06-21 11:05' },
    { name:'vault-notes',         path:'~/MeDocuments/Obsidian/vault-notes',                  agents:2,  running:false, last:'2026-06-28 09:30' },
  ];
  const PROJ_POOL = [   /* demo folders for "Open other folder…" (the real control opens the OS folder picker) */
    { name:'n8n-flows',     path:'~/MeDocuments/Automation/n8n-flows',            agents:0, running:false, last:'never' },
    { name:'gsd-workbench', path:'~/MeDocuments/AppData/Anthropic/gsd-workbench', agents:0, running:false, last:'never' },
  ];
  let projOpenIdx = 0;     /* index into PROJ of the open project, or null (the mockup ships one open) */
  let projFlashIdx = null; /* a freshly-registered row to flash once */
  function projStamp(){const d=new Date(),p=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;}
  function projAgentsLabel(p){if(!p.agents)return 'no agents yet';return `${p.agents} agent${p.agents===1?'':'s'}${p.running?' running':''}`;}
  function projRowHtml(p,i){
    const isOpen = projOpenIdx===i;
    const badge = isOpen
      ? `<span data-comp="connector-health-badge" class="hbadge hb-conn"><span class="hd" style="background:var(--success)"></span>Open</span>`
      : (p.running ? `<span data-comp="connector-health-badge" class="hbadge hb-warn">Agents running</span>` : '');
    const action = isOpen ? '' :
      `<button data-comp="button" class="btn-secondary btn-sm" onclick="projOpen(${i})" ${projOpenIdx!==null?'disabled title="One project at a time — close the current project first."':''}><i data-lucide="folder-open" class="w-3 h-3"></i>Open</button>`;
    return `<div data-comp="registry-row" data-variants="proj-flash" class="reg-row${isOpen?' proj-open':''}${projFlashIdx===i?' proj-flash':''}">`
      +`<div class="reg-main"><div class="reg-name">${p.name}</div><div class="reg-meta">${p.path} · ${projAgentsLabel(p)} · last opened ${p.last}</div></div>`
      +`<div class="reg-rt">${badge}${action}</div></div>`;
  }
  function projRender(){
    const list=document.getElementById('proj-list');if(!list)return;   /* not the mockup (no Projects pane) → no-op */
    const act=document.getElementById('proj-active'),empty=document.getElementById('proj-empty');
    if(projOpenIdx===null){ if(act)act.hidden=true; if(empty)empty.hidden=false; }
    else{
      const p=PROJ[projOpenIdx];
      const set=(id,html)=>{const el=document.getElementById(id);if(el)el.innerHTML=html;};
      set('proj-a-name',p.name); set('proj-a-path',p.path);
      set('proj-a-agents',p.agents?`<b>${p.agents}</b> agent${p.agents===1?'':'s'} attached`:'no agents yet');
      set('proj-a-opened',`${p.last} · just now`);
      if(act)act.hidden=false; if(empty)empty.hidden=true;
    }
    const cnt=document.getElementById('proj-count');if(cnt)cnt.textContent=`${PROJ.length} · open / register`;
    list.innerHTML=PROJ.map(projRowHtml).join('');
    projUpdateChip(); LU();
    if(projFlashIdx!==null){const row=list.querySelectorAll('.reg-row')[projFlashIdx];projFlashIdx=null;if(row){row.scrollIntoView({block:'nearest'});setTimeout(()=>row.classList.remove('proj-flash'),700);}}
  }
  function projUpdateChip(){
    const chip=document.getElementById('proj-chip'),nm=document.getElementById('proj-chip-nm');if(!chip||!nm)return;
    if(projOpenIdx===null){nm.textContent='No project';chip.title='No project open — open Settings → Projects';}
    else{nm.textContent=PROJ[projOpenIdx].name;chip.title='Active project — open Settings → Projects';}
  }
  function projOpen(i){
    if(projOpenIdx!==null)return;                 /* one project at a time — no second open path */
    projOpenIdx=i;const p=PROJ[i];p.last=projStamp();p.running=p.agents>0;
    projRender();toast(`Opened ${p.name} — the dashboard now works in this project.`);
  }
  function projAskClose(){const c=document.getElementById('proj-close-confirm');if(c)c.classList.add('show');}   /* always opens (never toggles) — dismiss is the ghost-x / Esc, per the confirm-gate precedent */
  function projCancelClose(){const c=document.getElementById('proj-close-confirm');if(c)c.classList.remove('show');}
  function projClose(stopAgents){
    if(projOpenIdx===null)return;const p=PROJ[projOpenIdx];projCancelClose();
    if(stopAgents){p.running=false;toast(`Closed ${p.name} — ${p.agents?p.agents+' agents stopped.':'no agents were running.'}`);}
    else          {toast(`Closed ${p.name} — ${p.agents?p.agents+' agents keep running in tmux.':'no agents were running.'}`);}
    p.last=projStamp();projOpenIdx=null;projRender();
  }
  function projOpenOther(){
    if(!PROJ_POOL.length){toast('No more demo folders — the real control opens the OS folder picker.');return;}
    const p=PROJ_POOL.shift();PROJ.push(p);projFlashIdx=PROJ.length-1;projRender();
    toast(`Registered ${p.name} — open it from the list.`);
  }
  function projInit(){ if(document.getElementById('proj-list'))projRender(); }

  /* ===== Past agents (Agent → Past) — the resume picker + the per-agent archive =====
     PAST mirrors the merged past-agents feed: every persisted agent that isn't live — dead roster records
     (src:'roster') plus archived records (src:'archive') — each with a resumable flag (has a conversation id
     to resume AND isn't live). ARCHIVE holds the full deep-freeze records behind the archive rows: a distinct
     archive id, the identity snapshot (colour/icon ride it), created/retired stamps, reserved lineage
     (parent · fork · handoff), the per-agent git author email, and the transcript REFERENCED in place. */
  const PAST=[
    {key:'pax', role:'tester',    name:'02 pax',  color:'var(--ag-turquoise)',icon:'ag-spider',model:'sonnet 4.6',src:'roster', resumable:true, stamp:'died 07-14 22:10', why:'tmux gone after reboot — cold-resumable on its conversation id'},
    {key:'juno',role:'coder',     name:'02 juno', color:'var(--ag-sapphire)', icon:'ag-golem', model:'opus 4.8',  src:'roster', resumable:false,stamp:'died 07-09 18:33', why:'no conversation id persisted — launched before id persistence; can\'t resume'},
    {key:'vera',role:'researcher',name:'03 vera', color:'var(--ag-orchid)',   icon:'ag-fox',   model:'opus 4.8',  src:'archive',resumable:true, stamp:'retired 07-12 17:40', arc:'arc-7f21c9'},
    {key:'otto',role:'reviewer',  name:'02 otto', color:'var(--ag-azure)',    icon:'ag-eagle', model:'sonnet 4.6',src:'archive',resumable:true, stamp:'retired 07-10 09:05', arc:'arc-b04e11'},
    {key:'mira',role:'planner',   name:'02 mira', color:'var(--ag-rose)',     icon:'ag-centurion',model:'haiku 4.5',src:'archive',resumable:true, stamp:'retired 07-06 15:22', arc:'arc-3d98a2'}
  ];
  const ARCHIVE=[
    {arc:'arc-7f21c9',role:'researcher',name:'03 vera',color:'var(--ag-orchid)',icon:'ag-fox',model:'opus 4.8',mode:'Ask',
     created:'07-08 10:12',retired:'07-12 17:40',cwd:'~/MeDocuments/…/awl-cc-dash',
     lineage:{parent:'researcher-01-sandy',fork:'turn 21',handoff:null},
     git:'researcher-03@agents.awl-cc-dash.invalid',transcript:'~/.claude/projects/…/9c2e41d7.jsonl'},
    {arc:'arc-b04e11',role:'reviewer',name:'02 otto',color:'var(--ag-azure)',icon:'ag-eagle',model:'sonnet 4.6',mode:'Edit',
     created:'07-04 08:50',retired:'07-10 09:05',cwd:'~/MeDocuments/…/awl-cc-dash',
     lineage:{parent:null,fork:null,handoff:'handoff-report-0704.md'},
     git:'reviewer-02@agents.awl-cc-dash.invalid',transcript:'~/.claude/projects/…/5aa10f38.jsonl'},
    {arc:'arc-3d98a2',role:'planner',name:'02 mira',color:'var(--ag-rose)',icon:'ag-centurion',model:'haiku 4.5',mode:'Plan',
     created:'06-30 13:15',retired:'07-06 15:22',cwd:'~/MeDocuments/…/awl-cc-dash',
     lineage:{parent:null,fork:null,handoff:null},
     git:'planner-02@agents.awl-cc-dash.invalid',transcript:'~/.claude/projects/…/e77c02b4.jsonl'}
  ];
  function pastRowHTML(p,i){const tile='<span class="agtile" style="width:var(--size-28);height:var(--size-28);color:'+p.color+'"><svg class="ag-svg"><use href="#'+p.icon+'"/></svg></span>';
    return '<div data-comp="past-agent-row" class="agrow past-row'+(p.resumable?'':' past-row--norez')+'" title="'+esc(p.why||p.model+' · '+p.stamp)+'">'
      +tile+'<span class="ag-lab"><span class="ag-role">'+p.role+' · '+p.model+'</span><span class="ag-name">'+p.name+'</span></span>'
      +'<span data-comp="past-source-badge" class="past-src'+(p.src==='archive'?' past-src--archive':'')+'" title="'+(p.src==='archive'?'From the archive — Resume un-retires it':'A dead roster record — the agent process is gone, the record persists')+'">'+p.src+'</span>'
      +'<span class="past-stamp">'+esc(p.stamp)+'</span>'
      +'<button data-comp="button" data-status="planned" class="btn btn-sm past-resume" '+(p.resumable?'':'disabled ')+'onclick="pastResume('+i+')" title="'+(p.resumable?'Resume — relaunch on the same conversation, same identity':'Can\'t resume — no conversation id to resume onto')+'"><i data-lucide="rotate-ccw" class="w-3 h-3"></i>Resume</button></div>';}
  function archLineage(l){if(!l||(!l.parent&&!l.fork&&!l.handoff))return '—';const bits=[];
    if(l.parent)bits.push('parent '+l.parent);if(l.fork)bits.push('fork @ '+l.fork);if(l.handoff)bits.push('handoff '+l.handoff);return bits.join(' · ');}
  function archRowHTML(a,i){const tile='<span class="agtile" style="width:var(--size-28);height:var(--size-28);color:'+a.color+'"><svg class="ag-svg"><use href="#'+a.icon+'"/></svg></span>';
    const kv=(k,v,plain)=>'<div class="arch-kv"><span class="k">'+k+'</span><span class="v'+(plain?' plain':'')+'">'+esc(v)+'</span></div>';
    return '<div data-comp="archive-row" class="fcard arch-card" data-arci="'+i+'">'
      +'<div class="fcard-head"><button class="fcard-exp" onclick="toggleFcard(this)" title="Expand the archive record">'+tile
      +'<span class="ag-lab"><span class="ag-role">'+a.role+'</span><span class="ag-name">'+a.name+'</span></span>'
      +'<span class="fcard-time">retired '+a.retired+'</span></button>'
      +'<button class="fcard-chevbtn" onclick="toggleFcard(this)" title="Expand / collapse"><i data-lucide="chevron-right" class="fcard-chev"></i></button></div>'
      +'<div class="fcard-body arch-body">'
      +kv('Archive id',a.arc)+kv('Created',a.created)+kv('Retired',a.retired)
      +kv('Model · mode',a.model+' · '+a.mode,true)+kv('CWD',a.cwd)
      +kv('Lineage',archLineage(a.lineage),!a.lineage||(!a.lineage.parent&&!a.lineage.fork&&!a.lineage.handoff))
      +kv('Git author',a.git)+kv('Transcript',a.transcript)
      +'<div class="arch-acts"><button data-comp="button" data-status="planned" class="btn btn-sm" onclick="archResume('+i+')" title="Resume — un-retires the agent back onto the roster, same conversation"><i data-lucide="rotate-ccw" class="w-3 h-3"></i>Resume</button>'
      +'<span class="flex-1"></span>'
      +'<button data-comp="button" class="btn-danger btn-sm" onclick="archDelete(this)" title="Delete forever — true-deletes this archive record (the referenced transcript is untouched)"><i data-lucide="trash-2" class="w-3 h-3"></i>Delete forever</button></div>'
      +'</div></div>';}
  function renderPast(){const pl=document.getElementById('past-list');if(pl)pl.innerHTML=PAST.map(pastRowHTML).join('');
    const al=document.getElementById('archive-list');if(al)al.innerHTML=ARCHIVE.map(archRowHTML).join('');
    const rez=PAST.filter(p=>p.resumable).length;
    const pc=document.getElementById('past-count');if(pc)pc.textContent=PAST.length+' past · '+rez+' resumable';
    const ac=document.getElementById('archive-count');if(ac)ac.textContent=ARCHIVE.length+' archived';
    const fn=document.getElementById('past-foot-note');if(fn)fn.textContent=PAST.length+' past agents · '+ARCHIVE.length+' archived — Resume relaunches on the same conversation, never a fork';
    LU();}
  function pastResume(i){const p=PAST[i];if(!p||!p.resumable)return;
    toast('Resuming '+p.role+' '+p.name+' — relaunching on its own conversation'+(p.src==='archive'?' (un-retired from the archive)':''));}
  function archResume(i){const a=ARCHIVE[i];if(!a)return;toast('Resuming '+a.role+' '+a.name+' — un-retired from the archive, same conversation');}
  function archDelete(btn){const card=btn.closest('.fcard');if(!card||card.querySelector('.arch-del-confirm'))return;
    const i=parseInt(card.dataset.arci,10);const a=ARCHIVE[i];if(!a)return;
    const c=document.createElement('div');c.setAttribute('data-comp','inline-confirm');c.className='tl-confirm foot-confirm--danger arch-del-confirm';c.style.display='flex';
    c.innerHTML='<span>Delete '+esc(a.name)+'’s archive record forever? This can’t be undone (the transcript it references is untouched).</span>';
    const cancel=document.createElement('button');cancel.className='btn btn-sm ml-auto';cancel.textContent='Cancel';cancel.onclick=e=>{e.stopPropagation();c.remove();};
    const go=document.createElement('button');go.className='btn-danger-solid btn-sm';go.innerHTML='<i data-lucide="trash-2" class="w-3.5 h-3.5"></i>Delete forever';
    go.onclick=e=>{e.stopPropagation();ARCHIVE.splice(i,1);const pi=PAST.findIndex(p=>p.arc===a.arc);if(pi>=0)PAST.splice(pi,1);
      renderPast();toast('Archive record '+a.arc+' deleted forever');};
    c.appendChild(cancel);c.appendChild(go);
    const head=card.querySelector('.fcard-head');if(head)head.insertAdjacentElement('afterend',c);else card.appendChild(c);LU();}

  /* ===== Import (Library header) — pull an external Claude session into the workspace =====
     Host decision (recorded in DESIGN.md → Library): the control lives on the LIBRARY panel header — every
     import lands as document-shaped content, and the Library already owns both the read surface (the
     line-numbered doc editor) and the onward routing to agents (the merged Export control). The drawer is an
     IN-FLOW surface under the header (tab panes push down; Esc / ghost-x closes). One engine, one selectable
     destination: agent (prompt queue) · read now (opens a read-only doc card) · file as doc. */
  const IMPORT_SESSIONS={
    web:[
      {t:'Dashboard design direction — quiet brutalism',d:'07-12',n:48},
      {t:'JWT rotation strategy — one-time vs sliding',d:'07-11',n:31},
      {t:'Electron sidecar lifecycle notes',d:'07-08',n:22},
      {t:'Agent naming brainstorm — human names',d:'07-05',n:17},
      {t:'OKLCH jewel palette derivation',d:'06-29',n:40}],
    desktop:[
      {t:'Local agent run — bridge poller profiling',d:'07-13',n:26},
      {t:'Sidecar storage model walkthrough',d:'07-10',n:35},
      {t:'tmux capture-pane quirks under WSL2',d:'07-07',n:19},
      {t:'Archive record shape review',d:'07-03',n:12}]};
  const IMPORT_SRC_NOTE={web:'claude.ai chats, listed by title',desktop:'the desktop app’s local sessions, read off disk'};
  let impSrc='web',impSel=null,impDest='agent',impAgent='max';
  function toggleImport(show){const d=document.getElementById('import-drawer');if(!d)return;
    const to=(show===undefined)?d.classList.contains('hidden'):!!show;d.classList.toggle('hidden',!to);
    if(to){renderImportList();renderImportAgents();LU();}}
  function impPickSrc(btn,src){segPick(btn);impSrc=src;impSel=null;
    const note=document.getElementById('imp-srcnote');if(note)note.textContent=IMPORT_SRC_NOTE[src]||'';
    const f=document.querySelector('#import-drawer .imp-filter input');if(f)f.value='';
    renderImportList();impSyncGo();}
  function impRowHTML(s,i,on){return '<button data-comp="import-session-row" class="imp-row'+(on?' on':'')+'" onclick="impPickSession(this,'+i+')"><span class="imp-t">'+esc(s.t)+'</span><span class="imp-meta">'+s.d+' · '+s.n+' messages</span></button>';}
  function renderImportList(){const el=document.getElementById('imp-list');if(!el)return;
    el.innerHTML=(IMPORT_SESSIONS[impSrc]||[]).map((s,i)=>impRowHTML(s,i,impSel===i)).join('');
    document.getElementById('import-drawer').classList.remove('empty');}
  function impPickSession(row,i){impSel=i;row.parentElement.querySelectorAll('.imp-row').forEach(r=>r.classList.toggle('on',r===row));impSyncGo();}
  function impFilter(inp){const q=inp.value.toLowerCase();const el=document.getElementById('imp-list');if(!el)return;let vis=0;
    [...el.querySelectorAll('.imp-row')].forEach(r=>{const hit=r.textContent.toLowerCase().includes(q);r.style.display=hit?'':'none';if(hit)vis++;});
    document.getElementById('import-drawer').classList.toggle('empty',vis===0);}
  function impPickDest(el,d){pickOpt(el);impDest=d;
    const ag=document.getElementById('imp-aglist');if(ag)ag.classList.toggle('show',d==='agent');impSyncGo();}
  function impAgentRowHTML(k,on){const a=AG[k];return '<button class="agrow'+(on?' on':'')+'" onclick="impPickAgent(this,\''+k+'\')" data-ag="'+k+'">'+agtileHTML(a)+'<span class="ag-lab"><span class="ag-role">'+a.role+'</span><span class="ag-name">'+a.name+'</span></span><i data-lucide="check" class="ag-ck"></i></button>';}
  function renderImportAgents(){const el=document.getElementById('imp-agrows');if(!el)return;
    el.innerHTML=AG_ORDER.map(k=>impAgentRowHTML(k,k===impAgent)).join('');}   /* the one shared roster, agents only — subagents/System are never addressable */
  function impPickAgent(row,k){impAgent=k;row.parentElement.querySelectorAll('.agrow').forEach(r=>r.classList.toggle('on',r===row));impSyncGo();}
  function impSyncGo(){const go=document.getElementById('imp-go');if(go)go.disabled=impSel==null;
    const note=document.getElementById('imp-sel-note');if(!note)return;
    const s=impSel!=null?(IMPORT_SESSIONS[impSrc]||[])[impSel]:null;
    note.textContent=s?('“'+s.t+'” → '+(impDest==='agent'?(AG[impAgent]?AG[impAgent].role+' '+AG[impAgent].name:'agent'):(impDest==='read'?'read now':'Documents'))):'Pick a session to import';}
  function runImport(){const s=impSel!=null?(IMPORT_SESSIONS[impSrc]||[])[impSel]:null;if(!s)return;
    const stub='# '+s.t+'\n\n> Imported from Claude ('+impSrc+') · '+s.n+' messages · exported '+s.d+'\n\nThe full conversation renders here — user/assistant turns, tool calls, and thinking, as clean markdown.';
    const slug=s.t.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'').slice(0,42)+'.md';
    if(impDest==='agent'){toast('Queued import → '+(AG[impAgent]?AG[impAgent].role+' '+AG[impAgent].name:'agent')+' — “'+s.t+'” lands on its prompt queue');toggleImport(false);return;}
    const d=createDoc(stub,slug);
    if(impDest==='read'){toggleImport(false);openEntry(d.key);toast('Imported for reading — opened in Documents (read-only)');}
    else{toggleImport(false);switchTab('doc','documents');const row=document.querySelector('.docnav-row[data-navid="'+d.key+'"]');if(row)row.scrollIntoView({block:'nearest'});toast('Imported → Documents · '+d.name);}}

  /* ============================ v9p10 ============================ */
  /* shared agent model + identity badges (one source of truth for badges everywhere).
     Next-up item 6: each agent's `subs` array is the ONE shared SUBAGENT roster — it mirrors that agent's
     Team card badge strip (the GROUND TRUTH: same ids, same run-state classes), and every other
     agent-listing surface (the feed From/To filter tree, Prompt To, the Compose/History From lists, the
     Link-pair dropdowns, the Details Subagents audit, the footer subagent total) renders from or reconciles
     to it — so rosters and counts can't drift. `type` is the audit's demo vocabulary. */
  const AG={
    user:{role:'human',name:'User',user:true},
    /* Next-up item 15: the reserved System pseudo-identity, parallel to User — a gear glyph on a navy tile
       (--ag-system, the --foreground ink register — never a jewel: System is the app, not an agent). It fronts
       Inbox ERROR cards for system-wide failures (infrastructure: tmux/WSL2/sidecar down · account-level:
       rate/usage caps, auth expiry · shared services: a global MCP outage) and badges LOG lines for system
       events. addressable:false encodes the rule in the roster data: FILTER-ONLY, never addressable (the
       subagent precedent) — it renders ONLY in the feed From/To filter tree (second, after User), never in
       Compose To, Compose From, or the History From filter (those iterate AG_ORDER, which excludes it). */
    system:{role:'app',name:'System',system:true,addressable:false},
    /* armed[] = the LAUNCH-GATED permission modes (§ Launch permissions): Bypass/Auto must be pre-armed at
       launch, and an un-armed mode is silently ABSENT from that agent's mode ring (repaintAgentPanel applies
       these flags to #mode-seg). Every agent whose current mode is Auto necessarily has 'auto' armed. */
    sandy:{role:'researcher',name:'01 sandy',color:'var(--ag-emerald)',icon:'ag-wizard',created:'06-26 14:30 · 2h12m',armed:['auto','bypass'],
      subs:[{id:'A1',st:'sb-active',type:'Explore'},{id:'A2',st:'sb-active',type:'Explore'},{id:'A3',st:'sb-active',type:'Explore'},{id:'A4',st:'sb-idle',type:'general-purpose'},{id:'A5',st:'sb-active',type:'code-reviewer'},{id:'A6',st:'sb-error',type:'general-purpose'}]},
    kai:{role:'synthesizer',name:'01 kai',color:'var(--ag-cobalt)',icon:'ag-golem',created:'06-25 09:12 · 1d',armed:['auto']},
    drew:{role:'auditor',name:'01 drew',color:'var(--ag-fern)',icon:'ag-gasmask',created:'06-26 15:48 · 54m',armed:[]},
    max:{role:'coder',name:'01 max',color:'var(--ag-amber)',icon:'ag-robot',created:'06-26 13:05 · 3h37m',armed:['auto'],
      subs:[{id:'A1',st:'sb-idle',type:'Explore'}]},
    rowan:{role:'researcher',name:'02 rowan',color:'var(--ag-crimson)',icon:'ag-fox',created:'06-26 11:20 · 5h22m',armed:['auto']},
    nova:{role:'tester',name:'01 nova',color:'var(--ag-violet)',icon:'ag-spider',created:'06-24 16:40 · 2d',armed:[]},
    vega:{role:'reviewer',name:'01 vega',color:'var(--ag-cyan)',icon:'ag-eagle',created:'06-26 16:02 · 40m',armed:['auto','bypass']},
    quinn:{role:'planner',name:'01 quinn',color:'var(--ag-vermilion)',icon:'ag-centurion',created:'06-23 08:15 · 3d',armed:[]},
    wren:{role:'docs',name:'01 wren',color:'var(--ag-citron)',icon:'ag-parrot',created:'06-26 10:05 · 6h37m',armed:['auto']},
    lex:{role:'designer',name:'01 lex',color:'var(--ag-magenta)',icon:'ag-tribal',created:'06-26 15:10 · 1h32m',armed:['auto'],
      subs:[{id:'A1',st:'sb-active',type:'Explore'},{id:'A2',st:'sb-active',type:'general-purpose'}]},
    sage:{role:'ops',name:'01 sage',color:'var(--ag-teal)',icon:'ag-astronaut',created:'06-22 14:00 · 4d',armed:['auto']},
    io:{role:'analyst',name:'01 io',color:'var(--ag-indigo)',icon:'ag-thirdeye',created:'06-26 16:25 · 17m',armed:[]},
    fen:{role:'scribe',name:'01 fen',color:'var(--ag-gold)',icon:'ag-cowled',created:'06-26 12:48 · 3h54m',armed:['auto'],
      subs:[{id:'A1',st:'sb-active',type:'Explore'},{id:'A2',st:'sb-active',type:'Explore'},{id:'A3',st:'sb-pending',type:'general-purpose'},{id:'B1',st:'sb-idle',type:'code-reviewer'},{id:'B2',st:'sb-active',type:'Explore'},{id:'B3',st:'sb-error',type:'general-purpose'},{id:'C1',st:'sb-pending',type:'Plan'},{id:'C2',st:'sb-active',type:'Explore'}]}
  };
  const AG_ORDER=['sandy','kai','drew','max','rowan','nova','vega','quinn','wren','lex','sage','io','fen'];
  function agtileHTML(a){return a.user
    ?'<span class="agtile agtile--user agtile--me"><i data-lucide="user" class="agtile-luc"></i></span>'
    :a.system
    ?'<span class="agtile agtile--system"><i data-lucide="settings" class="agtile-luc"></i></span>'   /* item 15: gear on navy — reads as WHO (an identity tile), not the Settings control */
    :'<span class="agtile" style="color:'+a.color+'"><svg class="ag-svg"><use href="#'+a.icon+'"/></svg></span>';}
  /* ND 5: the identity badge is TWO-TIER now — badgeHTML is the dense default (the old .badge-sm footprint,
     folded into the .badge base), badgeXsHTML the small tier (the .rcpt recipient footprint — tile + name only,
     var(--badge-m-h)) used by the review-rail nav cards and the History receiver badges (kept matched with the
     Transcript recipients). */
  function badgeHTML(a){return '<span data-comp="identity-badge" data-variants="sub" class="badge badge-c'+(a.user?' ag-user-badge':'')+'">'
    +agtileHTML(a)+'<span class="b-lab"><span class="b-role">'+a.role+'</span><span class="b-name">'+a.name+'</span></span></span>';}
  function badgeXsHTML(a){return '<span data-comp="identity-badge" data-variants="sub" class="badge-xs" title="'+a.role+' '+a.name+'">'
    +agtileHTML(a)+'<span class="bx-nm">'+esc(String(a.name).replace(/^\d+\s*/,''))+'</span></span>';}
  function agrowHTML(k,on){const a=AG[k];return '<button class="agrow'+(on?' on':'')+'" onclick="toggleAgRow(this)" data-ag="'+k+'">'
    +agtileHTML(a)+'<span class="ag-lab"><span class="ag-role">'+a.role+'</span><span class="ag-name">'+a.name+'</span></span><i data-lucide="check" class="ag-ck"></i></button>';}
  function fillAgLists(){document.querySelectorAll('[data-aglist]').forEach(el=>{el.innerHTML=AG_ORDER.map(k=>agrowHTML(k)).join('');});}
  /* ===== Next-up items 6+7: roster-rendered agent-selector lists ===== */
  /* ONE renderer fills every [data-agroster] .aglist mount from the shared AG roster (AG[k].subs mirrors the
     Team cards — the ground truth), so the feed From/To filter tree, Prompt To, the Compose-From source
     list, the History-From filter, and the Link-pair dropdowns can't drift from the cards or each other.
     Mount kinds: tree (User + the reserved System row + 2-level subagent tree — item 15: System is filter-only,
     so ONLY this mount includes it) · targets (Scratch + agents) · agents (agents only — the History From list) ·
     source / source-agents (single-select pickSource rows, with/without User).
     data-on / data-off = the demo selection; data-expand = a parent key whose sub-rows start expanded.
     The rendered markup is IDENTICAL in shape to the old hand-authored rows, so styles.css applies unchanged.
     Item 7: tree parents get a SELECTED/TOTAL .ag-subcount, kept live by updateSubCounts(). */
  const SUB_LAB={'sb-active':'running','sb-idle':'done','sb-pending':'waiting','sb-error':'error'};
  function agSubs(k){return (AG[k]&&AG[k].subs)||[];}
  function subRowHTML(par,s,on){return '<button class="agrow agrow--sub'+(on?' on':'')+'" onclick="toggleAgRow(this)" data-sub="'+s.id+'" data-par="'+par+'"><span class="sbadge '+s.st+' sub-fbadge">'+s.id+'</span><span class="ag-lab"><span class="ag-role">'+s.type+'</span><span class="ag-name">'+(SUB_LAB[s.st]||'')+'</span></span><i data-lucide="check" class="ag-ck"></i></button>';}
  function agrowTreeHTML(k,on,expand){const a=AG[k];const subs=agSubs(k);
    if(!subs.length)return agrowHTML(k,on);
    const n=subs.length,selN=on?n:0;   /* initial state: parent on = whole subtree on */
    const actN=subs.filter(s=>s.st==='sb-active').length;   /* the roster's subagent ACTIVE-vs-QUIET signal: a glance dot on the collapsed parent row (green = ≥1 running · muted = all quiet), so activity reads without expanding the subtree */
    return '<button class="agrow agrow--parent'+(on?' on':'')+(expand?' subs-open':'')+'" onclick="toggleAgRow(this)" data-ag="'+k+'">'
      +agtileHTML(a)+'<span class="ag-lab"><span class="ag-role">'+a.role+'</span><span class="ag-name">'+a.name+'</span></span>'
      +'<span data-comp="subagent-activity-dot" class="sub-actdot'+(actN?'':' quiet')+'" title="'+(actN?actN+' of '+n+' subagent'+(n===1?'':'s')+' running':'all '+n+' subagent'+(n===1?'':'s')+' quiet')+'"></span>'
      +'<span class="ag-subcount" title="'+selN+' of '+n+' subagent'+(n===1?'':'s')+' selected">'+selN+'/'+n+'</span>'
      +'<span class="ag-exp" onclick="toggleAgSubs(event,this)" title="Show subagents"><i data-lucide="chevron-right"></i></span><i data-lucide="check" class="ag-ck"></i></button>'
      +'<div class="agrow-subs'+(expand?' open':'')+'">'+subs.map(s=>subRowHTML(k,s,on)).join('')+'</div>';}
  function sourceRowHTML(k,on){const a=AG[k];return '<button class="agrow'+(on?' on':'')+'" onclick="pickSource(this)" data-ag="'+k+'">'+agtileHTML(a)+'<span class="ag-lab"><span class="ag-role">'+a.role+'</span><span class="ag-name">'+a.name+'</span></span><i data-lucide="check" class="ag-ck"></i></button>';}
  function scratchRowHTML(on){return '<button class="agrow'+(on?' on':'')+'" onclick="toggleAgRow(this)" data-ag="scratch"><span class="agtile agtile--user" style="background:var(--ag-azure)"><i data-lucide="file-text" class="agtile-luc"></i></span><span class="ag-lab"><span class="ag-role">scratchpad</span><span class="ag-name">Scratch</span></span><i data-lucide="check" class="ag-ck"></i></button>';}
  function fillRosterLists(){document.querySelectorAll('[data-agroster]').forEach(el=>{
      const kind=el.dataset.agroster;
      const on=new Set((el.dataset.on||'').split(',').filter(Boolean));
      const off=new Set((el.dataset.off||'').split(',').filter(Boolean));
      const expand=el.dataset.expand||'';
      let html='';
      if(kind==='tree')html=agrowHTML('user',!off.has('user'))+agrowHTML('system',!off.has('system'))+AG_ORDER.map(k=>agrowTreeHTML(k,!off.has(k),k===expand)).join('');   /* item 15: the reserved System row sits SECOND, after User — filter-only, tree mount only */
      else if(kind==='targets')html=scratchRowHTML(on.has('scratch'))+AG_ORDER.map(k=>agrowHTML(k,on.has(k))).join('');
      else if(kind==='agents')html=AG_ORDER.map(k=>agrowHTML(k,!off.has(k))).join('');   /* item 9: the History-From list = the To list minus Scratch */
      else if(kind==='source')html=sourceRowHTML('user',on.has('user'))+AG_ORDER.map(k=>sourceRowHTML(k,on.has(k))).join('');
      else if(kind==='source-agents')html=AG_ORDER.map(k=>sourceRowHTML(k,on.has(k))).join('');   /* the Link-pair endpoint lists (agents only) */
      el.innerHTML=html;});
    LU();}

  /* line-numbered markdown — the rendered line numbers MATCH the raw .md file, so "see line N" is a real reference */
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}   /* null-safe: L2's document-wide {sec:null} author seeds crashed the Authors lens via esc(null) (L2-panel find) */
  function inlineMd(s){s=esc(s);s=s.replace(/`([^`]+)`/g,'<span class="md-code-i">$1</span>');s=s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>');return s;}
  /* DOC EDITOR — an interactive left rail that indexes every line + section (click a cell to select a
     line or a whole section, so a chunk can be commented on / shared), the rendered body, and a docked
     comment popout. Shared by Plan bodies AND the README/CLAUDE/TODO tabs. Line numbers MATCH the raw
     file so "see line N" is a real reference. */
  function getFeedback(host){const e=entryById(host);return e?(e.feedback||[]):[];}   /* L1: unified — docs + plans both carry feedback[] on their entry */
  function fbCountsBySec(list){const m={};list.forEach(f=>{(m[f.sec]=m[f.sec]||{approve:0,revise:0,block:0})[f.verdict]++;});return m;}
  /* P4d: the rail badge is a SECTION anchor — its count is ALL verdicts on the section and a click opens
     every comment for that section (the worst-verdict colour stays as a severity hint). */
  function railBadge(host,sec,c){const worst=c.block?'block':(c.revise?'revise':'approve');const m=VERDICT[worst];const n=c.approve+c.revise+c.block;
    return '<span class="rd v-'+worst+'" title="Open '+n+' comment'+(n>1?'s':'')+' on '+esc(sec)+' →" onclick="event.stopPropagation();openCmtPop(\''+host+'\',\''+esc(sec)+'\')"><i data-lucide="'+m.ic+'"></i><span class="rd-n">'+n+'</span></span>';}
  /* AUTHORS lens — authorship metadata (agent + timestamp), tracked like comments. getAuthors mirrors getFeedback;
     the neutral users-glyph gutter badge (rd--author) parallels railBadge but opens the author box (openAuthorPop). */
  function getAuthors(host){const e=entryById(host);return e?(e.authors||[]):[];}   /* L1: unified — docs now share the same nav rail + Authors lens as plans (the doc-hosts-return-[] special case is gone) */
  function authorsBySec(list){const m={};list.forEach(f=>{(m[f.sec]=m[f.sec]||[]).push(f);});return m;}
  function authorBadge(host,sec,list){const n=list.length;const lab=sec||'the whole document';   /* ND 3b: sec='' = the document-wide group (the title-row gutter badge) */
    return '<span class="rd rd--author" title="Open '+n+' edit'+(n>1?'s':'')+' on '+esc(lab)+' →" onclick="event.stopPropagation();openAuthorPop(\''+host+'\',\''+esc(sec)+'\')"><i data-lucide="users"></i><span class="rd-n">'+n+'</span></span>';}
  function mdEditorHTML(host,text,mode){mode=mode||'feedback';   /* the gutter is lens-aware: feedback→verdict badges (revise/block only) · authors→neutral author badges · outline→no badges */
    const fb=mode==='feedback'?fbCountsBySec(getFeedback(host)):null;const au=mode==='authors'?authorsBySec(getAuthors(host)):null;
    const rows=text.split('\n').map((ln,i)=>{const n=i+1;const secid='s'+i;
      /* L2 (b): level-generic heading parse — ## .. #### → level = hash count; the title (#) stays whole-doc. */
      const isTitle=/^#\s+/.test(ln);const hm=ln.match(/^(#{2,4})\s+(.*)/);const isHead=!!hm;const level=isHead?hm[1].length:0;const sec=isHead?hm[2]:'';
      /* ND 3b: the DOC-WIDE author badge renders in the rail's TITLE cell too — the `# ` row's gutter now
         computes the document-wide {sec:null} author group (it used to be computed only for isHead rows,
         leaving the seeded whole-doc data invisible). */
      const c=isHead?(fb?fb[sec]:(au?au[sec]:null)):(isTitle&&au?au[null]:null);
      /* L2 (e): the feedback gutter chip renders ONLY for revise/block — an approved section shows none (absence = approved). */
      const gutter=c?(au?authorBadge(host,isTitle?'':sec,c):((c.revise||c.block)?railBadge(host,sec,c):'')):'';
      /* L2 (b/c): every heading row carries data-secid (unique line index) + data-hlevel; data-sec keeps the
         human name so feedback (keyed by name) still maps to the row. */
      const hAttrs=isHead?' data-secid="'+secid+'" data-hlevel="'+level+'" data-sec="'+esc(sec)+'"':'';
      const rail='<button class="md-rail'+(isHead?' is-sec':'')+(isTitle?' is-title':'')+'" onclick="railClick(event,\''+host+'\','+n+')" onmouseenter="railHover(this)" onmouseleave="railHoverOut(this)" data-line="'+n+'"'+hAttrs+(isTitle?' data-title="1"':'')+' title="'+(isTitle?'Select the whole document':(isHead?'Select this section':'Select line '+n))+'">'+gutter+'<span class="rn">'+n+'</span></button>';
      let body;
      if(isTitle)body='<span class="md-line md-h1">'+inlineMd(ln.replace(/^#\s+/,''))+'</span>';
      else if(isHead)body='<span class="md-line md-h'+level+'">'+inlineMd(sec)+'</span>';
      else if(/^\s*-\s*\[( |x|X)\]\s+/.test(ln)){const done=/\[(x|X)\]/.test(ln);const t=ln.replace(/^\s*-\s*\[( |x|X)\]\s+/,'');body='<span class="md-line md-task'+(done?' done':'')+'"><span class="md-box">'+(done?'☑':'☐')+'</span> '+inlineMd(t)+'</span>';}
      else if(ln.trim()==='')body='<span class="md-line md-blank"> </span>';
      else body='<span class="md-line">'+inlineMd(ln)+'</span>';
      return '<div data-comp="markdown-row" data-variants="revise block author" class="md-row'+(isHead?' md-h-row':'')+'" data-line="'+n+'"'+hAttrs+'>'+rail+body+'</div>';
    }).join('');
    /* A4 bullet 2 — trailing filler row continues the rail track to the bottom past the last line */
    return '<div data-comp="doc-editor" class="doc-ed" data-edhost="'+host+'"><div class="md">'+rows+'<div class="md-row md-fill" aria-hidden="true"><span class="md-rail md-rail--fill"></span><span class="md-line"></span></div></div><div data-comp="comment-popover" class="plan-cmt-pop"></div></div>';}
  /* per-host selection — pick a single line or a whole section so it can be commented on / shared */
  const SELby={};
  function setCmtCtl(host,on){const ctl=document.querySelector('[data-cmthost="'+host+'"]');if(ctl)ctl.classList.toggle('is-off',!on);}
  function clearSel(host){const ed=document.querySelector('[data-edhost="'+host+'"]');if(ed)ed.querySelectorAll('.md-row.rsel,.md-row.rsel-sec').forEach(r=>r.classList.remove('rsel','rsel-sec'));SELby[host]=null;setCmtCtl(host,false);eaUpdate(host);}
  /* L3 (5c): the comment/author popover rows are click-to-select — toggling .sel gathers the picked rows' text into
     SELby[host] as a 'box' selection so the SAME per-host merged Export control (eaUpdate/eaEmbed/expCopy) can Embed or
     Copy them into a prompt for follow-up. Extends the existing SELby store (a new 'box' kind) rather than adding a
     parallel one; the box selection is ephemeral — cleared when the popover closes (closeCmtPop). */
  function toggleBoxSel(row,host){row.classList.toggle('sel');const pop=popFor(host);if(!pop)return;
    const rows=[...pop.querySelectorAll('.cmt-pop-item.sel')];
    if(rows.length){
      /* L3-panel fix: a box selection REPLACES any rail line/section selection in the shared SELby slot — clear the
         rail's visuals + Comment control too, or they'd stay lit against a selection that no longer exists. */
      if(!SELby[host]||SELby[host].kind!=='box'){const ed=document.querySelector('[data-edhost="'+host+'"]');if(ed)ed.querySelectorAll('.md-row.rsel,.md-row.rsel-sec').forEach(r=>r.classList.remove('rsel','rsel-sec'));setCmtCtl(host,false);}
      const text=rows.map(r=>{const t=r.querySelector('.cpi-txt');return t?t.textContent.trim():'';}).filter(Boolean).join('\n\n');
      const noun=pop.querySelector('.cph-ic')?'edit':'comment';   /* the Authors box carries a users-glyph .cph-ic; the comment box does not */
      SELby[host]={kind:'box',ref:'box',label:rows.length+' '+noun+(rows.length>1?'s':''),boxText:text};}
    else SELby[host]=null;
    eaUpdate(host);}
  /* L2 (c): the ONE section-boundary helper — a level-L heading's section spans from its heading row to the
     next heading row of level ≤ L (exclusive), stopping before the trailing filler row. Anchored by the
     heading's unique data-secid (its line index) so repeated sub-heading names can never collide. Used by
     railClick (select), railHover (preview), and highlightFbSection (feedback sync). */
  function sectionRows(host,secid){const ed=document.querySelector('[data-edhost="'+host+'"]');if(!ed)return [];
    const head=ed.querySelector('.md-row.md-h-row[data-secid="'+secid+'"]');if(!head)return [];
    const L=parseInt(head.dataset.hlevel,10);const rows=[head];let nx=head.nextElementSibling;
    while(nx&&!nx.classList.contains('md-fill')){
      if(nx.classList.contains('md-h-row')&&parseInt(nx.dataset.hlevel,10)<=L)break;
      rows.push(nx);nx=nx.nextElementSibling;}
    return rows;}
  function railClick(e,host,n){e.stopPropagation();const ed=document.querySelector('[data-edhost="'+host+'"]');if(!ed)return;
    const row=ed.querySelector('.md-row[data-line="'+n+'"]');if(!row)return;
    const isTitle=!!row.querySelector('.md-h1');const isHead=row.classList.contains('md-h-row');const secid=row.dataset.secid;const cur=SELby[host];
    /* re-clicking the active selection clears it (sections compare by data-secid, not by name) */
    if(cur&&((cur.kind==='all'&&isTitle)||(cur.kind==='sec'&&isHead&&cur.ref===secid)||(cur.kind==='line'&&cur.ref===n))){clearSel(host);return;}
    ed.querySelectorAll('.md-row.rsel,.md-row.rsel-sec').forEach(r=>r.classList.remove('rsel','rsel-sec'));
    if(isTitle){/* the title selects the whole document */ ed.querySelectorAll('.md-row').forEach(r=>r.classList.add(r.querySelector('.md-h1')?'rsel':'rsel-sec'));
      SELby[host]={kind:'all',ref:'all',label:'Whole doc'};}   /* ND 3d: the doc-wide label reads "Whole doc" */
    else if(isHead){/* L2 (c): nested boundary via sectionRows — spans sub-headings until the next same-or-higher heading */
      const rows=sectionRows(host,secid);rows.forEach((r,i)=>r.classList.add(i===0?'rsel':'rsel-sec'));
      SELby[host]={kind:'sec',ref:secid,sec:row.dataset.sec,label:'§ '+row.dataset.sec};}
    else{row.classList.add('rsel');SELby[host]={kind:'line',ref:n,label:'Line '+n};}
    setCmtCtl(host,true);eaUpdate(host);}
  /* A4 bullet 2 — rail-hover preview: light every row a CLICK would select, in canvas cream (.hl).
     line → that (wrapped) row · section → the whole section · title → the whole document (filler row excluded). */
  function railHover(el){const ed=el.closest('.doc-ed');if(!ed)return;const row=el.closest('.md-row');let rows;
    if(el.dataset.title)rows=[...ed.querySelectorAll('.md-row')].filter(r=>!r.classList.contains('md-fill'));
    else if(el.dataset.secid)rows=sectionRows(ed.dataset.edhost,el.dataset.secid);   /* L2 (c): preview the whole nested span */
    else rows=[row];
    rows.forEach(r=>r.classList.add('hl'));}
  function railHoverOut(el){const ed=el.closest('.doc-ed');if(ed)ed.querySelectorAll('.md-row.hl').forEach(r=>r.classList.remove('hl'));}
  /* L1 (ND 1-6): renderDocs mirrors renderPlans — DOCS.map(planCardHTML) fills #doc-list, the shared entry-nav fills
     #doc-nav (+ the Add-document affordance), and the Documents tab carries a draft+review count chip (docs-badge).
     The per-doc .docdoc panes + one-at-a-time docPick switching are retired; each doc card carries its own working
     raw-markdown edit toggle (entryEdit) and the FULL plan footer (Export · Reviewer · Revise·Reject·Approve). */
  function renderDocs(){const el=document.getElementById('doc-list');if(el)el.innerHTML=DOCS.map(planCardHTML).join('');
    renderEntryNav('doc-nav',DOCS,'doc');
    const b=document.getElementById('docs-badge');if(b){const n=DOCS.filter(d=>d.status==='review'||d.status==='draft').length;b.textContent=n;b.style.display=n?'':'none';}
    LU();}

  /* 3-state verdicts (stroke icons, verdict-colored): Approve / Revise / Block */
  const VERDICT={approve:{ic:'circle-check',cls:'v-approve',lab:'Approve'},revise:{ic:'triangle-alert',cls:'v-revise',lab:'Revise'},block:{ic:'circle-x',cls:'v-block',lab:'Block'}};
  function verdictBadgeHTML(v){const m=VERDICT[v];return '<span data-comp="verdict-badge" class="vbadge '+m.cls+'"><i data-lucide="'+m.ic+'"></i>'+m.lab+'</span>';}
  /* thumbs agree / disagree toggle (default = agree) — reused in the composer, the comment popout, + nav cards */
  function thumbsHTML(){return '<span class="thumbs" onclick="event.stopPropagation()"><button data-comp="agree-toggle" type="button" class="thumb up on" title="Agree" onclick="thumbPick(this)"><i data-lucide="thumbs-up"></i></button><button type="button" class="thumb down" title="Disagree" onclick="thumbPick(this)"><i data-lucide="thumbs-down"></i></button></span>';}
  function thumbPick(b){const w=b.closest('.thumbs');if(!w)return;w.querySelectorAll('.thumb').forEach(t=>t.classList.remove('on'));b.classList.add('on');}
  /* L1: DOC_FB is retired — doc feedback seeds now live on each DOCS entry's feedback[] (folded in below). */
  function popFor(host){const ed=document.querySelector('[data-edhost="'+host+'"]');return ed?ed.querySelector('.plan-cmt-pop'):null;}
  /* v9p14c: the THREE comment indicators move together — the selected feedback card (teal fill), its
     highlighted section text (teal), and the open comment popout. openCmtPop is the single sync point
     (the Feedback nav cards AND the rail-gutter verdict badges both route through it), closeCmtPop clears
     all three, and opening a different comment switches all three. */
  function clearFbHL(host){const ed=document.querySelector('[data-edhost="'+host+'"]');if(ed)ed.querySelectorAll('.md-row.fbhl,.md-row.fbhl-sec').forEach(r=>r.classList.remove('fbhl','fbhl-sec'));}
  function highlightFbSection(host,sec){const ed=document.querySelector('[data-edhost="'+host+'"]');if(!ed)return;clearFbHL(host);
    /* L2 (c): feedback is keyed by section NAME; find its heading row, then span the nested section by data-secid */
    const head=[...ed.querySelectorAll('.md-row.md-h-row')].find(r=>r.dataset.sec===sec);if(!head)return;
    sectionRows(host,head.dataset.secid).forEach((r,i)=>r.classList.add(i===0?'fbhl':'fbhl-sec'));}
  function deselectNavCards(host){const nav=document.querySelector('[data-plannav="'+host+'"]');if(nav)nav.querySelectorAll('.fb-card.sel').forEach(c=>c.classList.remove('sel'));}
  function selectMatchingCards(host,sec){const nav=document.querySelector('[data-plannav="'+host+'"]');if(!nav)return;   /* P4d: section anchor — select every card in the section */
    nav.querySelectorAll('.fb-card').forEach(c=>c.classList.toggle('sel',c.dataset.fbsec===sec));}
  function navCardClick(card,host,sec){if(card.classList.contains('sel')){closeCmtPop(host);return;}if(card.classList.contains('au-card'))openAuthorPop(host,sec);else openCmtPop(host,sec);}
  /* comment popout (docked under the body, same width): merged verdict badge + section badge header;
     each response carries an agent badge, time, and a thumbs agree toggle */
  /* P4d: section-anchored popout — lists EVERY comment on the section (all verdicts), each row carrying its
     own verdict badge + thumbs. The header drops the single-verdict badge; the count matches the contents. */
  function openCmtPop(host,sec){const list=getFeedback(host);const pop=popFor(host);if(!pop)return;
    dropBoxSel(host);   /* L3-panel fix: the popover content is being replaced — a box selection from the previous section is stale (Export would act on invisible content) */
    const items=list.filter(f=>f.sec===sec);
    /* ND 4d: row-1 order is badge · verdict · spacer · timestamp · THUMBS — the thumbs right-align after the
       right-aligned time (they live ONLY here, never on the nav cards). L3 (5c): each row is click-to-select
       (toggleBoxSel) → the merged Export control can Embed/Copy the picked comment(s). */
    pop.innerHTML='<div class="cmt-pop-head"><span class="sel-badge">§ '+esc(sec)+'</span><span class="cph-time" style="margin-left:auto">'+items.length+' comment'+(items.length===1?'':'s')+'</span><button data-comp="ghost-icon-button" class="ghost-ic" title="Close" onclick="closeCmtPop(\''+host+'\')"><i data-lucide="x"></i></button></div>'
      +'<div class="cmt-pop-body">'+items.map(f=>{const a=AG[f.ag];
        return '<div class="cmt-pop-item" role="button" tabindex="0" title="Select to add to a prompt (Export → Embed / Copy)" onclick="toggleBoxSel(this,\''+host+'\')"><div class="cpi-h">'+badgeHTML(a)+verdictBadgeHTML(f.verdict)+'<span class="flex-1"></span><span class="cph-time">'+(f.time||'')+'</span>'+thumbsHTML()+'</div>'+(f.comment?'<div class="cpi-txt">'+esc(f.comment)+'</div>':'<div class="cpi-none">no comment left</div>')+'</div>';}).join('')+'</div>';
    pop.classList.add('open');LU();selectMatchingCards(host,sec);highlightFbSection(host,sec);pop.scrollIntoView({block:'nearest',behavior:'smooth'});}
  function closeCmtPop(host){const pop=popFor(host);if(pop){pop.classList.remove('open');pop.innerHTML='';}deselectNavCards(host);clearFbHL(host);
    /* L3 (5c): the popover box selection lives only while the popover is open — drop it + re-gate Export on close */
    dropBoxSel(host);}
  /* L3-panel fix: drop a stale 'box' selection + re-gate Export (shared by popover close AND popover switch) */
  function dropBoxSel(host){if(SELby[host]&&SELby[host].kind==='box'){SELby[host]=null;eaUpdate(host);}}
  /* AUTHORS box — the docked popout in the Authors lens: a neutral section-anchor header (users glyph + § section +
     "N edits") and ONE entry per gutter-badge count (agent badge + timestamp, no verdict/comment/thumbs). Routes
     through the SAME three-indicator sync spine as openCmtPop (card fill + section highlight + open box). */
  /* L3 (5a): each author-box row uses the comment-box layout grammar minus the thumbs — row 1 = agent badge + a
     Drafted/Edited/Revised action badge (a neutral .dbadge variant, .au-act) + the timestamp right-aligned; row 2 =
     the edit summary (wraps). L3 (5c): rows are click-to-select (toggleBoxSel) so an edit can be embedded in a prompt. */
  function authorActionBadge(action){return '<span data-comp="contribution-badge" data-variants="drafted edited revised" class="dbadge au-act">'+esc(action||'Edited')+'</span>';}   /* ND 11c: the contribution badge is its own component now (its three action states declared on the element — the retired gallery-specimen leg's replacement) */
  function openAuthorPop(host,sec){const list=getAuthors(host);const pop=popFor(host);if(!pop)return;
    dropBoxSel(host);   /* L3-panel fix: same stale-box drop as openCmtPop */
    /* L3: key ''/null to the ONE document-wide group (L2's {sec:null} draft seed) — navCardClick passes '' for it;
       the header then reads "Whole document" (the title-cell register) rather than an empty "§" badge. */
    const items=list.filter(f=>(f.sec||'')===(sec||''));const secLab=sec?('§ '+esc(sec)):'Whole doc';   /* ND 3d */
    pop.innerHTML='<div class="cmt-pop-head"><span class="cph-ic"><i data-lucide="users"></i></span><span class="sel-badge">'+secLab+'</span><span class="cph-time" style="margin-left:auto">'+items.length+' edit'+(items.length===1?'':'s')+'</span><button data-comp="ghost-icon-button" class="ghost-ic" title="Close" onclick="closeCmtPop(\''+host+'\')"><i data-lucide="x"></i></button></div>'
      +'<div class="cmt-pop-body">'+items.map(f=>{const a=AG[f.ag];
        return '<div class="cmt-pop-item" role="button" tabindex="0" title="Select to add to a prompt (Export → Embed / Copy)" onclick="toggleBoxSel(this,\''+host+'\')"><div class="cpi-h">'+badgeHTML(a)+authorActionBadge(f.action)+'<span class="flex-1"></span><span class="cph-time cph-time--clk"><i data-lucide="clock" class="au-clk"></i>'+(f.time||'')+'</span></div>'+(f.summary?'<div class="cpi-txt">'+esc(f.summary)+'</div>':'')+'</div>';}).join('')+'</div>';
    pop.classList.add('open');LU();selectMatchingCards(host,sec);highlightFbSection(host,sec);pop.scrollIntoView({block:'nearest',behavior:'smooth'});}
  /* v9p14c: a small "Mark as" verdict dropdown lives INSIDE the composer (the Comment control is now a
     plain button); pick a verdict here, then Save commits it */
  function verdictDropdownHTML(verdict){return '<span data-comp="verdict-dropdown" data-variants="approve revise block" class="vdd" data-vdd data-verdict="'+verdict+'">'
    +'<button type="button" class="vdd-trig" onclick="toggleVdd(this)">'+verdictBadgeHTML(verdict)+'<i data-lucide="chevron-down" class="vdd-cv"></i></button>'
    +'<span class="vdd-menu">'+['approve','revise','block'].map(v=>'<button type="button" class="vdd-opt" onclick="pickVdd(this,\''+v+'\')">'+verdictBadgeHTML(v)+'</button>').join('')+'</span></span>';}
  function toggleVdd(btn){const dd=btn.closest('.vdd');document.querySelectorAll('.vdd.open').forEach(x=>{if(x!==dd)x.classList.remove('open');});dd.classList.toggle('open');}
  function pickVdd(opt,v){const dd=opt.closest('.vdd');dd.dataset.verdict=v;dd.querySelector('.vdd-trig').innerHTML=verdictBadgeHTML(v)+'<i data-lucide="chevron-down" class="vdd-cv"></i>';dd.classList.remove('open');LU();
    const ed=opt.closest('.doc-ed');if(ed&&typeof syncCommentSave==='function')syncCommentSave(ed.dataset.edhost);}   /* L2 (f): a verdict switch re-checks the comment-required rule */
  /* user comment composer — opens in the same popout for the current line/section selection */
  function openComposer(host,verdict){const sel=SELby[host];if(!sel||sel.kind==='box'){toast('Select a line or section first');return;}const pop=popFor(host);if(!pop)return;   /* L3 (5c): a popover box selection isn't a line/section to comment on */
    deselectNavCards(host);clearFbHL(host);   /* composing is a separate flow from viewing existing feedback */
    pop.innerHTML='<div class="cmt-pop-head"><span class="sel-badge">'+esc(sel.label)+'</span><span class="cph-lab">New comment</span><span class="flex-1"></span><button data-comp="ghost-icon-button" class="ghost-ic" title="Close" onclick="closeCmtPop(\''+host+'\')"><i data-lucide="x"></i></button></div>'
      +'<div class="cmt-pop-body"><div class="cmt-compose"><div class="cpi-h">'+badgeHTML(AG.user)+'<span class="cph-lab" style="margin-left:var(--space-2)">Mark as</span>'+verdictDropdownHTML(verdict)+'<span class="flex-1"></span>'+thumbsHTML()+'</div>'
      +'<textarea class="in cmt-ta" oninput="syncCommentSave(\''+host+'\')" placeholder="Add a comment or tags…"></textarea>'
      +'<div class="cmt-foot"><span class="cmt-req"></span><span class="flex-1"></span><button data-comp="button" class="btn btn-sm" onclick="closeCmtPop(\''+host+'\')">Cancel</button><button data-comp="button" class="btn-main btn-sm cmt-save" onclick="saveComment(\''+host+'\')"><i data-lucide="check" class="w-3.5 h-3.5"></i>Save</button></div></div></div>';
    pop.classList.add('open');LU();syncCommentSave(host);pop.scrollIntoView({block:'nearest',behavior:'smooth'});}
  /* L2 (f): a revise/block verdict REQUIRES a non-empty comment — keep Save disabled (+ a hint) until the note
     is typed; approve stays comment-optional. Re-run on every keystroke and on a verdict switch. */
  function syncCommentSave(host){const pop=popFor(host);if(!pop)return;const btn=pop.querySelector('.cmt-save');if(!btn)return;
    const vdd=pop.querySelector('[data-vdd]');const v=vdd?vdd.dataset.verdict:'approve';
    const ta=pop.querySelector('.cmt-ta');const txt=ta?ta.value.trim():'';const need=(v==='revise'||v==='block')&&!txt;
    btn.disabled=need;btn.title=need?VERDICT[v].lab+' needs a comment':'Save';
    const req=pop.querySelector('.cmt-req');if(req)req.textContent=need?VERDICT[v].lab+' needs a comment':'';}
  function openComposerFromCtl(btn){const ctl=btn.closest('[data-cmthost]');if(!ctl)return;if(ctl.classList.contains('is-off')){toast('Select a line or section first');return;}openComposer(ctl.dataset.cmthost,ctl.dataset.verdict||'approve');}
  function saveComment(host){const pop=popFor(host);const vdd=pop?pop.querySelector('[data-vdd]'):null;const v=vdd?vdd.dataset.verdict:'approve';
    const ta=pop?pop.querySelector('.cmt-ta'):null;const txt=ta?ta.value.trim():'';const sel=SELby[host];
    /* L2 (f): a revise/block verdict REQUIRES a note (the Save button is also disabled for this — belt + braces);
       approve is comment-optional and, comment-less, surfaces only in the reviewer roster. */
    if((v==='revise'||v==='block')&&!txt){toast(VERDICT[v].lab+' needs a comment');if(ta)ta.focus();return;}
    /* Q3=B: append to the entry's feedback + re-render so tally/outline dot/rail badge/Feedback count update (thumbs stay cosmetic).
       L2 (c): the comment keys by section NAME (sel.sec) while DOM selection was anchored on sel.ref (data-secid). */
    const e=entryById(host);const list=e?e.feedback:null;
    if(list&&sel&&sel.kind==='sec')list.push({sec:sel.sec,ag:'user',verdict:v,time:'now',comment:txt});
    closeCmtPop(host);
    (host.indexOf('doc-')===0?renderDocs:renderPlans)();reopenPlan(host);planNavMode(host,'feedback');   /* L1: docs re-render like plans, then reopen + switch to the Feedback lens */
    toast('Comment saved — marked '+VERDICT[v].lab);}
  function openFeedback(host){if(document.getElementById(host))planNavMode(host,'feedback');}

  /* PLANS — seeded from real ~/.claude/plans/*.md markdown (rendered verbatim, line-numbered) */
  const PLANS=[
    {id:'plan-1',file:'auth-token-rotation-shimmering-falcon.md',status:'review',title:'Auth token-rotation remediation',owner:'sandy',open:true,created:'Jun 18 09:12',createdAgo:'3d',edited:'Jun 20 14:07',editedAgo:'17h',
     md:`# Auth token-rotation remediation

## Context
The JWT middleware accepts expired tokens: \`validateToken()\` never checks the \`exp\` claim, and refresh issues a fresh token indefinitely. Any held refresh token keeps a session alive forever.

## Approach
Enforce \`exp\` in \`validateToken()\`, add sliding-window refresh rotation behind a feature flag, and cover the rotation path with a regression test before merge.

## Steps
- [x] Reproduce the expiry bypass under token reuse
- [x] Enforce \`exp\` in \`validateToken()\`
- [ ] Add sliding-window refresh rotation
- [ ] Gate behind feature flag \`auth.rotation\`
- [ ] Add a regression test for the rotation path
- [ ] Open a PR & request review from reviewer-01

## Risks
Rotation churn under load; mitigate with a short overlap window. Keep the flag default-off until staging smoke passes.

## TL;DR
Close the expiry-bypass path with \`exp\` enforcement plus flagged refresh rotation, covered by a regression test, before merging to main.`,
     feedback:[
       {sec:'Context',ag:'sandy',verdict:'approve',time:'14:38',comment:''},
       {sec:'Approach',ag:'vega',verdict:'revise',time:'14:44',comment:'Prefer one-time rotation over sliding-window for replay safety — sliding-window leaves a valid window open after a token is stolen.'},
       {sec:'Approach',ag:'drew',verdict:'approve',time:'14:46',comment:''},
       {sec:'Approach',ag:'rowan',verdict:'block',time:'14:49',comment:'Block until the Risks rollback path lands — do not merge rotation without a way to unwind churn on prod.'},
       {sec:'Steps',ag:'drew',verdict:'approve',time:'14:47',comment:'Order is right; add an explicit negative test for an already-expired refresh token.'},
       {sec:'Risks',ag:'kai',verdict:'block',time:'14:51',comment:'Need a rollback path if rotation churn spikes auth latency on prod before this can ship.'}
     ],
     authors:[
       {sec:null,ag:'sandy',action:'Drafted',time:'Jun 18 09:12',summary:'Drafted the initial remediation plan — context, approach, steps, and risks.'},
       {sec:'Context',ag:'sandy',action:'Edited',time:'Jun 18 09:12',summary:'Wrote up the expired-token bypass and its blast radius.'},
       {sec:'Approach',ag:'sandy',action:'Edited',time:'Jun 18 10:40',summary:'Laid out exp enforcement plus flagged sliding-window rotation.'},
       {sec:'Approach',ag:'vega',action:'Revised',time:'Jun 19 15:22',summary:'Weighed one-time rotation against sliding-window for replay safety.'},
       {sec:'Steps',ag:'drew',action:'Edited',time:'Jun 19 16:05',summary:'Added a negative test for an already-expired refresh token.'},
       {sec:'Steps',ag:'sandy',action:'Edited',time:'Jun 20 08:44',summary:'Reordered the steps and marked the exp-enforcement work done.'},
       {sec:'Risks',ag:'kai',action:'Revised',time:'Jun 20 11:10',summary:'Called out rotation-churn latency and the need for a rollback path.'},
       {sec:'TL;DR',ag:'wren',action:'Edited',time:'Jun 20 14:07',summary:'Tightened the summary to a single sentence.'}
     ]},
    {id:'plan-2',file:'session-handoff-export-quiet-harbor.md',status:'approved',title:'Session-handoff transcript export',owner:'wren',open:false,created:'Jun 12 16:40',createdAgo:'9d',edited:'Jun 19 09:21',editedAgo:'2d',
     md:`# Session-handoff transcript export

## Context
A finished agent's context should hand cleanly to the next session instead of being lost when the run ends.

## Steps
- [x] Define the transcript schema
- [x] Serialize messages + tool calls
- [x] Write a summary.md alongside
- [x] Wire export() into the CLI

## TL;DR
Structured JSONL transcript export so an agent's context survives a handoff.`,
     feedback:[{sec:'Steps',ag:'sandy',verdict:'approve',time:'09:18',comment:'Verified the export round-trips on a 200-turn session.'}],
     authors:[{sec:null,ag:'wren',action:'Drafted',time:'Jun 12 16:40',summary:'Drafted the session-handoff export plan.'},{sec:'Context',ag:'wren',action:'Edited',time:'Jun 12 16:40',summary:'Framed the clean-handoff goal.'},{sec:'Steps',ag:'wren',action:'Edited',time:'Jun 18 11:20',summary:'Listed schema → serialize → summary → CLI wiring.'},{sec:'Steps',ag:'sandy',action:'Revised',time:'Jun 19 09:05',summary:'Verified the export round-trips on a 200-turn session and marked the steps done.'}]},
    {id:'plan-3',file:'dashboard-layout-reflow-electric-meadow.md',status:'draft',title:'Dashboard layout reflow',owner:'lex',open:false,created:'Jun 20 10:50',createdAgo:'20h',edited:'Jun 20 11:02',editedAgo:'20h',
     md:`# Dashboard layout reflow

## Context
Reflow the three-pane frame and add the Documentation panel without regressing the resize behavior across the nested panel groups.

## Steps
- [x] Audit the current panel structure & handlers
- [ ] Draft the new column reading order
- [ ] Move Prompts into the right column
- [ ] Insert the Documentation panel
- [ ] Verify resize across the nested groups

## TL;DR
Reading order becomes Agent · Team Graph · Documentation · Feed · Prompt, with resize intact.`,
     feedback:[],
     authors:[{sec:null,ag:'lex',action:'Drafted',time:'Jun 20 10:50',summary:'Drafted the dashboard layout-reflow plan.'},{sec:'Context',ag:'lex',action:'Edited',time:'Jun 20 10:50',summary:'Framed the reflow goal without regressing resize.'},{sec:'Steps',ag:'lex',action:'Edited',time:'Jun 20 11:02',summary:'Sketched the audit → reorder → move → insert → verify steps.'},{sec:'Steps',ag:'lex',action:'Revised',time:'Jun 20 11:30',summary:'Reordered the steps after the structure audit.'}]}   /* ND 3a: lex now carries all THREE distinct actions (Drafted/Edited/Revised) so the 3-badge overlap stack is exercised in the Authors roster */
  ];
  /* L1 (ND-1): DOCS — the project docs as reviewable-document entries in the SAME shape as PLANS (id doc-*, file,
     status, title, owner, created/edited, md, feedback[], authors[]) so the whole Plans machinery — the 3-row card,
     the Outline/Feedback/Authors rail, the decision footer, the two-column entry-nav — serves docs unchanged.
     Statuses are a deliberate mix (draft · in review · approved) so the lifecycle badge renders meaningfully. `path`
     is the FULL path (it disambiguates the project vs user CLAUDE.md); the entry-nav derives its name + directory
     line from it, and `file` is the disambiguated card-row label. md content is moved verbatim from the retired doc textareas. */
  const DOCS=[
    {id:'doc-readme',file:'README.md',path:'agent-dashboard/README.md',status:'review',title:'Project README',owner:'lex',open:false,created:'Jun 17',createdAgo:'7d',edited:'Jun 20',editedAgo:'17h',
     md:`# AWL Multi-Agent Dashboard

A control surface for running and supervising a team of Claude Code agents from one window. Watch the team, steer each agent, and review their work without leaving the dashboard.

## The five panels
The window is a title bar over three columns over a status footer.

### Left column
- **Agent** — inspect & configure the selected agent.

### Middle column
- **Team** — every agent as a live card.
- **Library** — plans + project docs (README, CLAUDE) and reference assets.

#### Library tabs
Plans, Documents, and Assets share one reviewable-document surface.

### Right column
- **Feed** — messages, scratchpad, log, inbox.
- **Prompts** — compose and dispatch prompts.

## Design system
Neobrutalism: hard 4px shadows, 2px borders, a warm cream canvas, and a single pink-to-teal emphasis ladder.

### Tokens
Every value lives in tokens.css — colours, type, spacing, radius, shadow.

### Components
styles.css holds the shared component CSS; behavior.js the interaction logic.`,
     feedback:[{sec:'The five panels',ag:'wren',verdict:'revise',time:'Jun 19',comment:'List Library before Feed so the doc order matches the new reading order.'}],
     authors:[{sec:null,ag:'lex',action:'Drafted',time:'Jun 17 09:00',summary:'Drafted the README — panels overview and design-system notes.'},{sec:'The five panels',ag:'lex',action:'Edited',time:'Jun 18 10:00',summary:'Expanded the five-panels section with the Library tabs.'},{sec:'Design system',ag:'lex',action:'Edited',time:'Jun 20 09:30',summary:'Added the tokens / components breakdown.'}]},
    {id:'doc-claude',file:'CLAUDE.md',path:'agent-dashboard/CLAUDE.md',status:'draft',title:'Project instructions',owner:'sandy',open:false,created:'Jun 16',createdAgo:'8d',edited:'Jun 21',editedAgo:'9h',
     md:`# CLAUDE.md

Project instructions loaded into every agent's context. Keep it short — it is spent context on every turn.

## Workspace identity
A general-purpose VS Code workspace for AI/agentic workflows. Current focus: the AWL multi-agent dashboard.

## Behavioral rules
- Stay inside the project directory unless told otherwise.
- Keep DEVLOG.md current — an unlogged change never happened.
- Write transient artifacts into .scratch/, never the repo root.
- Preserve everything you weren't asked to change.`,
     feedback:[],
     authors:[{sec:null,ag:'sandy',action:'Drafted',time:'Jun 16 12:00',summary:'Drafted the project CLAUDE.md instructions.'},{sec:'Workspace identity',ag:'sandy',action:'Edited',time:'Jun 16 12:00',summary:'Described the workspace focus.'},{sec:'Behavioral rules',ag:'sandy',action:'Revised',time:'Jun 21 08:45',summary:'Revised the behavioral rules — scope, DEVLOG, scratch, preservation.'}]},
    {id:'doc-claudeuser',file:'CLAUDE.md (user)',path:'~/.claude/CLAUDE.md',status:'approved',title:'User instructions',owner:'wren',open:false,created:'May 28',createdAgo:'27d',edited:'Jun 22',editedAgo:'2d',
     md:`# CLAUDE.md

User-level instructions loaded into every project's context, on top of the project CLAUDE.md. Global defaults that travel with you.

## Working style
- Be direct, practical, low-ceremony. Lead with action.
- Prefer dedicated tools over ad-hoc shell for file search and edits.
- Write generated artifacts outside any repo, under a scratch path.

## Conventions
- Use markdown links for file references, not bare paths.
- Match the project's existing patterns before introducing new ones.`,
     feedback:[{sec:'Working style',ag:'sandy',verdict:'approve',time:'Jun 22',comment:'Reads clean — good to keep as the standing default.'}],
     authors:[{sec:null,ag:'wren',action:'Drafted',time:'May 28 09:00',summary:'Drafted the user-level instructions.'},{sec:'Working style',ag:'wren',action:'Edited',time:'May 28 09:00',summary:'Set the direct, low-ceremony working style.'},{sec:'Conventions',ag:'wren',action:'Revised',time:'Jun 22 11:20',summary:'Revised the conventions — markdown links and pattern-matching.'}]},
    {id:'doc-notes',file:'notes.md',path:'agent-dashboard/notes.md',status:'draft',title:'Scratch notes',owner:'lex',open:false,created:'Jun 26',createdAgo:'1d',edited:'Jun 26',editedAgo:'4h',
     md:`# Scratch notes

Short-lived notes for the current run — kept brief on purpose.

## Endpoints
- Sidecar API — http://127.0.0.1:7690
- Renderer dev — http://127.0.0.1:5199`,
     feedback:[],
     authors:[{sec:null,ag:'lex',action:'Drafted',time:'Jun 26 10:15',summary:'Drafted the scratch notes for the current run.'},{sec:'Endpoints',ag:'lex',action:'Edited',time:'Jun 26 10:15',summary:'Noted the sidecar + renderer dev endpoints.'}]}
  ];
  /* L1 (ND-2): the single entry lookup — search PLANS then DOCS (doc-* ids resolve to DOCS). Replaces the scattered
     PLANS.find(x=>x.id===…) lookups so planAct / reopenPlan / planNavMode / saveComment / getFeedback / getAuthors
     all operate on plans and docs through one path. */
  function entryById(id){return PLANS.find(x=>x.id===id)||DOCS.find(x=>x.id===id)||null;}
  const PLAN_BADGE={review:['db-review','In review'],approved:['db-approved','Approved'],draft:['db-draft','Draft']};
  function fbBySection(p){const m={};p.feedback.forEach(f=>{(m[f.sec]=m[f.sec]||{approve:0,revise:0,block:0})[f.verdict]++;});return m;}
  function planNavHTML(p,fb,mode){
    /* L2 (b): a level-generic parse — headings ##..#### carry their level; each outline item is anchored to the
       heading's LINE INDEX (data-secid), never its text, so repeated sub-headings can't collide. */
    const heads=[];p.md.split('\n').forEach((l,i)=>{const m=l.match(/^(#{2,4})\s+(.*)/);if(m)heads.push({level:m[1].length,text:m[2],secid:'s'+i,line:i+1});});
    /* ND 3c: the entry's right-hand number is the heading's LINE NUMBER (the revise/block dot already signals
       "this section has feedback", so the old feedback count lost no signal). */
    const outline=heads.map(h=>{const c=fb[h.text];const worst=c?(c.block?'d-block':(c.revise?'d-revise':'')):'';   /* L2 (e): approve no longer tints the dot — only revise/block survive */
      return '<button data-comp="outline-item" class="ol-item" style="--hl:'+h.level+'" data-hlevel="'+h.level+'" data-secid="'+h.secid+'" onclick="planJump(\''+p.id+'\',this)"><span class="ol-dot '+worst+'"></span><span class="ol-nm">'+esc(h.text)+'</span><span class="ol-c" title="line '+h.line+'">'+h.line+'</span></button>';}).join('');
    const auN=(p.authors||[]).length;   /* ND 1b: the lens strip's text tab reads "TOC" (its body caption stays "Table of contents"), freeing width so the nav could narrow; Feedback + Authors stay icon+count tabs splitting the second half */
    const tabs='<div class="nav-tabs">'
      +'<button data-comp="nav-tab" class="nav-tab nav-tab--ol '+(mode==='outline'?'on':'')+'" onclick="planNavMode(\''+p.id+'\',\'outline\')" title="TOC — table of contents"><span class="nt-ic"><i data-lucide="list"></i></span><span class="nt-lab">TOC</span></button>'
      +'<button data-comp="nav-tab" class="nav-tab nav-tab--fb '+(mode==='feedback'?'on':'')+'" onclick="planNavMode(\''+p.id+'\',\'feedback\')" title="Feedback"><span class="nt-ic"><i data-lucide="message-square"></i></span><span class="nt-lab">Feedback</span>'+(p.feedback.length?'<span class="nav-cnt">'+p.feedback.length+'</span>':'')+'</button>'
      +'<button data-comp="nav-tab" class="nav-tab nav-tab--au '+(mode==='authors'?'on':'')+'" onclick="planNavMode(\''+p.id+'\',\'authors\')" title="Authors"><span class="nt-ic"><i data-lucide="users"></i></span><span class="nt-lab">Authors</span>'+(auN?'<span class="nav-cnt">'+auN+'</span>':'')+'</button>'
      +'</div>';
    /* ND 1e: in the outline lens the "Table of contents" caption lives INSIDE .ol-scroll, so it scrolls with the
       content (TOC / Authors / Reviewers each carry their own heading; navy hairlines divide the three groups). */
    const body=mode==='feedback'?('<div class="ol-cap">Feedback</div>'+feedbackListHTML(p.id,p.feedback))
      :mode==='authors'?('<div class="ol-cap">Authors</div>'+authorListHTML(p.id,p.authors||[]))
      :('<div class="ol-scroll"><div class="ol-cap">Table of contents</div><div class="ol-list">'+outline+'</div>'+outlineRostersHTML(p)+'</div>');
    return tabs+body;}
  /* L2 (d): the two Outline rosters — distinct Authors, then distinct Reviewers, stacked under the TOC. A reviewer
     row trails its WORST revise/block verdict (block>revise), or a lone Approve for an approve-only reviewer —
     encoding the two-level model (reviewer verdicts are distinct from the document's own lifecycle badge / footer Approve). */
  function rosterAgents(list){const seen=[];(list||[]).forEach(f=>{if(f.ag&&seen.indexOf(f.ag)<0)seen.push(f.ag);});return seen;}
  function worstVerdict(list,ag){let w='approve';(list||[]).forEach(f=>{if(f.ag===ag){if(f.verdict==='block')w='block';else if(f.verdict==='revise'&&w!=='block')w='revise';}});return w;}
  /* ND 3a: an Authors-roster row carries its agent's CONTRIBUTION badge(s) — deduped to distinct action TYPES
     (Drafted / Edited / Revised, at most 3, in that order) and stacked as count-aware overlapping text badges
     (2 overlap a little, 3 more; hover fans the stack out — the .au-stack CSS). */
  function authorActions(list,ag){const order=['Drafted','Edited','Revised'];const acts=[];(list||[]).forEach(f=>{if(f.ag===ag&&f.action&&acts.indexOf(f.action)<0)acts.push(f.action);});return order.filter(x=>acts.indexOf(x)>=0);}
  function actionStackHTML(acts){if(!acts.length)return '';
    return '<span data-comp="contribution-badge-stack" data-variants="n2 n3" class="au-stack n'+acts.length+'" title="'+acts.join(' · ')+'">'+acts.map(a=>authorActionBadge(a)).join('')+'</span>';}
  function rosterBlockHTML(cls,label,rows){return '<div data-comp="outline-roster" class="ol-roster '+cls+'"><div class="ol-rhead"><span class="ol-rlab">'+label+'</span><span class="nav-cnt">'+rows.length+'</span></div>'
    +(rows.length?'<div class="ol-rlist">'+rows.join('')+'</div>':'<div class="ol-rempty">None yet</div>')+'</div>';}
  function outlineRostersHTML(p){
    const au=rosterAgents(p.authors).map(k=>'<div class="ol-rrow">'+badgeHTML(AG[k])+actionStackHTML(authorActions(p.authors,k))+'</div>');
    const rev=rosterAgents(p.feedback).map(k=>'<div class="ol-rrow">'+badgeHTML(AG[k])+verdictBadgeHTML(worstVerdict(p.feedback,k))+'</div>');
    return rosterBlockHTML('ol-roster--au','Authors',au)+rosterBlockHTML('ol-roster--rev','Reviewers',rev);}
  /* ND 2a: SECTION-GROUPED feedback cards — ONE card per section (1:1 with the rail's gutter badges), which
     kills the old "clicking one nav card selects every card in that section" defect at the model level (the
     per-entry cards shared a data-fbsec; now the section IS the card) and closes the feedback↔rail mapping
     drift in the same move. Row 1 = the § section badge; then, per contributing REVISE/BLOCK agent, a
     right-aligned timestamp row over an (agent badge + verdict badge) row. No thumbs (they live only in the
     badge popover) and no comment preview (uniform card height). APPROVE verdicts emit NO card — approval is
     implied by absence and surfaces only in the Reviewers roster; a section with nothing but approvals gets
     no feedback card. */
  function feedbackListHTML(host,list){
    const secs=[];list.forEach(f=>{if((f.verdict==='revise'||f.verdict==='block')&&f.sec&&secs.indexOf(f.sec)<0)secs.push(f.sec);});
    if(!secs.length)return '<div class="fb-empty">No revise/block feedback —<br>approvals read from the Reviewers roster.</div>';
    return '<div class="fb-list">'+secs.map(sec=>{
      const rows=list.filter(f=>f.sec===sec&&(f.verdict==='revise'||f.verdict==='block'));
      return '<div data-comp="feedback-card" class="fb-card" role="button" tabindex="0" data-fbsec="'+esc(sec)+'" onclick="navCardClick(this,\''+host+'\',\''+esc(sec)+'\')" title="Open all comments on this section →">'
        +'<div class="fb-top"><span class="sel-badge">§ '+esc(sec)+'</span></div>'
        +rows.map(f=>'<div class="fbs-time"><i data-lucide="clock" class="au-clk"></i><span>'+(f.time||'')+'</span></div>'
          +'<div class="fbs-row">'+badgeXsHTML(AG[f.ag])+verdictBadgeHTML(f.verdict)+'</div>').join('')
        +'</div>';}).join('')+'</div>';}
  /* ND 2b: AUTHORSHIP cards take the same section-grouped shape — one card per section (the document-wide
     {sec:null} entries group under a "Whole doc" card), each per-agent row carrying the CONTRIBUTION badge
     (Drafted / Edited / Revised) instead of a verdict. Supersedes the earlier per-entry "N2" author-card layout. */
  function authorListHTML(host,list){if(!list.length)return '<div class="fb-empty">No authorship recorded yet.</div>';
    const secs=[];list.forEach(f=>{const k=f.sec||'';if(secs.indexOf(k)<0)secs.push(k);});
    return '<div class="fb-list">'+secs.map(sec=>{
      const rows=list.filter(f=>(f.sec||'')===sec);
      return '<div data-comp="author-card" class="fb-card au-card" role="button" tabindex="0" data-fbsec="'+esc(sec)+'" onclick="navCardClick(this,\''+host+'\',\''+esc(sec)+'\')" title="Open all edits on this section →">'
        +'<div class="fb-top"><span class="sel-badge">'+(sec?'§ '+esc(sec):'Whole doc')+'</span></div>'
        +rows.map(f=>'<div class="fbs-time"><i data-lucide="clock" class="au-clk"></i><span>'+(f.time||'')+'</span></div>'
          +'<div class="fbs-row">'+badgeXsHTML(AG[f.ag])+authorActionBadge(f.action)+'</div>').join('')
        +'</div>';}).join('')+'</div>';}
  /* R-batch item 10: the Plans footer leads with the merged Export control, then the single-agent Review chip (both
     left-aligned); the right action group is just the decision trio (Revise · Reject · Approve). The right group
     wraps (Approve drops to its own line, still right-aligned) so nothing clips at narrow widths. */
  function planFootHTML(p){let right;
    if(p.status==='approved')right='<span class="text-[9px] font-bold font-mono" style="color:var(--success)">Approved 14:09</span>';
    else right='<button data-comp="button" class="btn-secondary" onclick="planAct(\'revise\',\''+p.id+'\')" title="Send the flagged sections back to the agent to revise"><i data-lucide="wand-sparkles" class="w-3.5 h-3.5"></i>Revise</button><button data-comp="button" class="btn-danger" onclick="planAct(\'reject\',\''+p.id+'\')"><i data-lucide="x" class="w-3.5 h-3.5"></i>Reject</button><button data-comp="button" class="btn-main" onclick="planAct(\'approve\',\''+p.id+'\')"><i data-lucide="check" class="w-3.5 h-3.5"></i>Approve</button>';
    return '<div class="plan-foot">'   /* item 10: [Export][reviewer chip] left · [Revise·Reject·Approve] right */
      +expMenuHTML(p.id)+reviewChipHTML(p.id)
      +'<div class="plan-foot-right">'+right+'</div></div>';}
  /* L3 (item 4): 2-row header — row 1 [owner badge · title · steps chip · spacer · review count-chips · lifecycle badge];
     row 2 [filename · spacer · created/edited]. The steps chip is promoted inline with the title (glance altitude);
     the cnt-strip stays for the glance tally while the L2 Reviewers roster carries the per-reviewer detail. */
  function planCardHTML(p){const a=AG[p.owner];const bb=PLAN_BADGE[p.status];const fb=fbBySection(p);const isDoc=p.id.indexOf('doc-')===0;
    const done=p.md.split('\n').filter(l=>/^\s*-\s*\[(x|X)\]/.test(l)).length;
    const stepN=p.md.split('\n').filter(l=>/^\s*-\s*\[( |x|X)\]/.test(l)).length;
    const tot={approve:0,revise:0,block:0};p.feedback.forEach(f=>tot[f.verdict]++);
    let fbadges='';['approve','revise','block'].forEach(v=>{if(tot[v]){const m=VERDICT[v];fbadges+='<span data-comp="count-chip" class="cnt-chip c-'+v+'" title="'+tot[v]+' '+m.lab.toLowerCase()+'"><i data-lucide="'+m.ic+'"></i><span class="cn">'+tot[v]+'</span></span>';}});
    /* item 4: the steps chip is promoted onto row 1 right after the title (compact "N/N steps"); hidden when
       stepN===0, which is naturally Plans-only (docs carry no checklist so the checkbox regex yields 0). */
    const steps=stepN?'<span data-comp="count-chip" class="cnt-chip c-steps'+(done===stepN?' all':'')+'" title="'+done+' of '+stepN+' steps done"><i data-lucide="list-checks"></i><span class="cn">'+done+'/'+stepN+' steps</span></span>':'';
    /* L3 (5d): plan AND doc cards both get the raw-markdown edit toggle (host-generic entryEdit) + the hidden
       textarea + a mic bound to it; planAct stays for approve/reject/revise only (its 'edit' branch is now dead).
       ND 14: the filename moves into the shared Editor header (after the "Editor" label) and the steps chip
       takes its old row-2 slot, right under the owner badge; hidden on a collapsed card is acceptable — the
       name still shows in the entry nav. */
    const editHead=editHeadHTML("entryEdit(this,'"+p.id+"')",p.id,'',p.id+'-ta',p.file);
    const rawTa='<textarea class="entry-edit" id="'+p.id+'-ta" style="display:none">'+esc(p.md)+'</textarea>';
    return '<div data-comp="plan-card" data-variants="flash" class="plan-card'+(p.open?' open':'')+'" id="'+p.id+'">'
      +'<button class="plan-head" onclick="togglePlan(this)"><div class="plan-head-main">'
      +'<div class="plan-row r1">'+badgeHTML(a)+'<span class="plan-title">'+p.title+'</span><span class="flex-1"></span><span class="cnt-strip">'+fbadges+'</span><span data-comp="lifecycle-badge" data-variants="sent" class="dbadge '+bb[0]+'">'+bb[1]+'</span></div>'
      +'<div class="plan-row r2">'+steps+'<span class="flex-1"></span><span class="plan-dates"><b>Created</b> '+p.created+' · '+p.createdAgo+' ago&nbsp;&nbsp;<b>Edited</b> '+p.edited+' · '+p.editedAgo+' ago</span></div>'
      +'</div><i data-lucide="chevron-right" class="plan-chev"></i></button>'
      +'<div class="plan-body">'   /* A4 bullet 1: editHeadHTML moved INSIDE .plan-main (below) so the Editor header sits over the editor box only; the Outline/Feedback/Authors nav rail rises full-height (Documents-style) */
      +'<div class="plan-rev"><div class="plan-nav" data-plannav="'+p.id+'">'+planNavHTML(p,fb,'outline')+'</div>'
      +'<div class="plan-main">'+editHead+mdEditorHTML(p.id,p.md,'outline')+rawTa+'</div></div>'
      +planFootHTML(p)+'</div></div>';}
  /* L1 (ND 1+2): one entry-nav mini-card for the two-column list, shared by Plans and Documents. Row 1 = icon + name
     (+ a path line for docs — they need it to disambiguate same-named files); row 2 = the lifecycle .dbadge. A row
     click opens/scrolls/flashes its card (navPick→openEntry); docs keep the rename ghost, plans list by title. */
  function entryNavRowHTML(e,kind){const bb=PLAN_BADGE[e.status];const on=e.open?' on':'';
    /* ND 4c: the leading icon is gone — a generic file-text / clipboard glyph conveyed no type for these lists
       (Assets keep their leading slot: it carries a real thumbnail / file-type split there, ND 10). */
    let name,path='',acts='';
    if(kind==='doc'){const fn=e.path.split('/').pop();const dir=e.path.slice(0,e.path.length-fn.length);
      name='<span class="docnav-name">'+esc(fn)+'</span>';path='<span class="docnav-path">'+esc(dir)+'</span>';acts=navActsHTML();}
    else{name='<span class="docnav-name">'+esc(e.title)+'</span>';}
    return '<div class="docnav-row navcard'+on+'" role="button" tabindex="0" data-navid="'+e.id+'" onclick="navPick(this)">'
      +'<div class="docnav-top"><span class="docnav-lab">'+name+path+'</span>'+acts+'</div>'
      +'<div class="docnav-life"><span data-comp="lifecycle-badge" class="dbadge '+bb[0]+'">'+bb[1]+'</span></div></div>';}
  /* L1: fill an entry-nav column from a list; Documents also gets the Add-document affordance at the foot */
  function renderEntryNav(navId,entries,kind){const nav=document.getElementById(navId);if(!nav)return;
    nav.innerHTML=entries.map(e=>entryNavRowHTML(e,kind)).join('')+(kind==='doc'?addMenuHTML('documents'):'');LU();}
  function renderPlans(){const el=document.getElementById('plan-list');if(el)el.innerHTML=PLANS.map(planCardHTML).join('');
    renderEntryNav('plan-nav',PLANS,'plan');   /* L1: the Plans tab gets the same two-column entry-nav as Documents */
    const b=document.getElementById('plans-badge');if(b){const n=PLANS.filter(p=>p.status==='review'||p.status==='draft').length;b.textContent=n;b.style.display=n?'':'none';}
    const sc=document.getElementById('plan-subtitle-count');if(sc){const rev=PLANS.filter(p=>p.status==='review').length;sc.textContent=PLANS.length+' plan'+(PLANS.length===1?'':'s')+' · '+rev+' awaiting review';}   /* L1: live counts replace the hardcoded subtitle */
    LU();}
  /* the tab strip is a LENS SWITCH: selecting a tab repaints the nav card list AND the editor gutter badges AND
     resets the docked box together (Outline→no gutter badges · Feedback→verdict badges · Authors→author badges). */
  function planNavMode(id,mode){const p=entryById(id);const nav=document.querySelector('[data-plannav="'+id+'"]');if(!nav||!p)return;
    /* L1-panel fix: switching lens while the card is in raw-edit mode used to repaint a fresh VISIBLE .doc-ed
       on top of the still-open textarea (Edit ghost stuck on "Save"). Exit edit first as an implicit SAVE —
       entryEdit re-seeds the textarea from entry.md on entry, so discarding here would lose typed work. */
    const card=document.getElementById(id);const ta=card?card.querySelector('.entry-edit'):null;
    if(ta&&ta.style.display!=='none'){p.md=ta.value;ta.style.display='none';
      const eb=card.querySelector('.lib-edit-head [title="Save"]');if(eb){eb.innerHTML='<i data-lucide="square-pen"></i>';eb.title='Edit';}}
    nav.innerHTML=planNavHTML(p,fbBySection(p),mode);
    const ed=document.querySelector('[data-edhost="'+id+'"]');if(ed)ed.outerHTML=mdEditorHTML(id,p.md,mode);   /* repaint the gutter to match the lens (the fresh .doc-ed carries an empty, closed popout) */
    clearSel(id);   /* reset any line/section selection + the Comment control so they match the fresh editor */
    if(typeof refreshJumpPills==='function')refreshJumpPills();   /* the swapped .md is a fresh scroll region — re-attach its jump-to-end pill (the discarded node took its pill with it) */
    LU();}
  function planJump(id,btn){const card=document.getElementById(id);if(!card)return;const secid=btn.dataset.secid;
    const nav=card.querySelector('[data-plannav]');if(nav)nav.querySelectorAll('.ol-item').forEach(o=>o.classList.toggle('on',o===btn));
    /* L2 (c): resolve the outline item to its exact heading row by data-secid (line index), never by text —
       then select the whole nested span through railClick → sectionRows. */
    const row=card.querySelector('.md-row.md-h-row[data-secid="'+secid+'"]');
    if(row){row.scrollIntoView({block:'nearest',behavior:'smooth'});
      railClick({stopPropagation(){}}, id, parseInt(row.dataset.line,10));}}

  /* FEED + HISTORY — expandable cards (Plan-style) with two-line agent badges; checkbox = multi-select */
  /* (ND 6d: dirTag — the Sent/Recv direction badges — is DELETED everywhere: direction reads from the
     sender → recipient arrow in the card header; the Sent/Received filters still gate on each entry's dir.) */
  /* recipient mini-badge — every message carries a typed recipients[] (user | <agent-id> | scratch, default
     [user]). It's ADDRESSED-TO / routing (drives the From/To filter + Sent/Received direction), NOT visibility —
     every message still shows regardless. Rendered as a deliberately-SMALLER identity badge (the recipient-badge
     exception) after the sender: sender → "→" → recipient(s) → status → dir. Reuses agent identity (tile + short
     name); User and Scratch are the two non-agent recipients. */
  function recipientBadge(rid){
    if(rid==='user')return '<span data-comp="recipient-badge" data-variants="scratch" class="rcpt" title="addressed to User"><span class="agtile agtile--user agtile--me"><i data-lucide="user" class="agtile-luc"></i></span><span class="rcpt-nm">User</span></span>';
    if(rid==='scratch')return '<span data-comp="recipient-badge" class="rcpt" title="addressed to the shared Scratchpad"><span class="agtile rcpt-scratch"><i data-lucide="notebook-pen" class="agtile-luc"></i></span><span class="rcpt-nm">Scratch</span></span>';
    const a=AG[rid];if(!a)return '';
    return '<span data-comp="recipient-badge" class="rcpt" title="addressed to '+a.role+' '+a.name+'"><span class="agtile" style="color:'+a.color+'"><svg class="ag-svg"><use href="#'+a.icon+'"/></svg></span><span class="rcpt-nm">'+a.name.replace(/^\d+\s*/,'')+'</span></span>';}
  function recipientsHTML(o){const r=(o.recipients&&o.recipients.length)?o.recipients:['user'];const CAP=2;
    const shown=r.slice(0,CAP).map(recipientBadge).join('');
    const more=r.length>CAP?'<span class="rcpt-more" title="'+esc(r.slice(CAP).join(', '))+'">+'+(r.length-CAP)+'</span>':'';
    return '<span class="rcpt-to" title="addressed to"><i data-lucide="arrow-right"></i></span>'+shown+more;}
  /* typed message content blocks — rendered in the expanded card; the Include toggles show/hide them by kind */
  /* A7: the block TYPE is now shown by the rail tag (3-char, in the rail box), so the block CONTENT carries NO inline
     label. (The old .msg-blk-lbl "BASH"/"DIFF" content labels are gone.) */
  function msgBlockHTML(b){
    if(b.k==='diff'){const lines=b.t.split('\n').map(l=>{const c=l[0]==='+'?'blk-add':(l[0]==='-'?'blk-del':'');return '<span class="'+c+'">'+esc(l)+'</span>';}).join('\n');
      return '<div data-comp="msg-block" class="msg-blk blk-diff" data-blk="diff">'+lines+'</div>';}
    return '<div data-comp="msg-block" class="msg-blk blk-'+b.k+'" data-blk="'+b.k+'">'+esc(b.t)+'</div>';}
  function msgBlocksHTML(o){return (o.blocks&&o.blocks.length)?'<div class="msg-blocks">'+o.blocks.map(msgBlockHTML).join('')+'</div>':'';}
  /* ND 6b: the rail marker is the block-type ICON — the same icon its content filter carries — replacing the
     old 3-char text abbreviations. Kind → filter mapping: text→Messages · think→Thinking · read/write/edit/
     file/diff→Files · bash/shell→Shell · search→Search · workflow→Workflow; meta rows keep a small info glyph
     (they have no filter and always show). Title row = no marker. */
  const RAIL_ICON={text:'message-square',think:'brain',read:'file-text',write:'file-text',edit:'file-text',file:'file-text',diff:'file-text',bash:'terminal',shell:'terminal',search:'search',workflow:'workflow',meta:'info'};
  function railTag(k){return '<span class="rail-tag" title="'+k+'"><i data-lucide="'+(RAIL_ICON[k]||'file-text')+'"></i></span>';}
  /* apply the Transcript minibar: Sent/Received hide whole cards by direction; the content filters hide block
     rows by kind-set; the far-end Subagent toggle (ND 6c) hides the nested subagent entries. */
  function applyTxFilters(){const bar=document.querySelector('#feed-transcript .minibar');if(!bar)return;
    const tog=lbl=>{const b=[...bar.querySelectorAll('.minitog')].find(x=>x.textContent.trim()===lbl);return b?b.classList.contains('on'):true;};
    const dirOn={out:tog('Sent'),in:tog('Received')};
    /* ND 6b: Messages · Thinking · Files (Read/Write/Edit) · Shell (Bash/PowerShell) · Search (Grep) · Workflow
       — Diff and Meta are dropped as filters (a diff files under Files; meta rows always show). */
    const km={Messages:['text'],Thinking:['think'],Files:['read','write','edit','file','diff'],Shell:['bash','shell'],Search:['search'],Workflow:['workflow']};
    const kind={};Object.keys(km).forEach(l=>{const on=tog(l);km[l].forEach(k=>{kind[k]=on;});});
    const subsOn=tog('Subagent');
    document.querySelectorAll('#tx-list .txcard').forEach(c=>{const o=MSGS[+c.dataset.msgi];if(o&&o.dir)c.style.display=dirOn[o.dir]?'':'none';});
    document.querySelectorAll('#tx-list .tx-sub').forEach(s=>{s.style.display=subsOn?'':'none';});
    /* P1b: hide whole block ROWS (rail + content) so only currently-visible blocks are selectable; a hidden block can't stay selected */
    document.querySelectorAll('#tx-list .mrow[data-blk],#tx-list .mrow[data-mblk="text"]').forEach(r=>{const k=r.dataset.blk||r.dataset.mblk;const vis=kind[k]!==false;r.style.display=vis?'':'none';if(!vis)r.classList.remove('bsel');});}
  /* P1b: a Transcript card uses the shared select-to-act model — click the header to select the WHOLE card
     (teal, multi + select-all), a per-block rail to select one block, the chevron to expand (select ≠ expand).
     Scratch still uses fcardHTML. ND 6d: the Sent/Recv direction tags are DELETED — direction reads from the
     sender → recipient arrow in the header — and the STATE badge moves right (after the preview text, before
     the right-aligned timestamp) on every transcript card. ND 6c: `subs` = the indices of this parent's nested
     subagent entries, appended inside the card body in communication order. */
  function txCardHTML(o,i,subs){const a=AG[o.ag];return '<div data-comp="message-card" data-variants="reply-flash" class="fcard txcard" data-selcard data-msgi="'+i+'">'
    +'<div class="fcard-head">'
    +'<button class="fcard-exp msel-head" onclick="txWholeSel(event,this)" title="Select this whole message (Attach)">'
    +badgeHTML(a)   /* A7: agent badge LEADS, at the dense-default size */
    +recipientsHTML(o)   /* → recipient mini-badge(s) — who it's addressed to (routing = the direction signal) */
    +'<span class="fcard-prev">'+o.body+'</span>'
    +(o.status?'<span data-comp="lifecycle-badge" class="dbadge db-'+o.status+'">'+({active:'Active',complete:'Complete',error:'Error'}[o.status]||'Complete')+'</span>':'')
    +'<span class="fcard-time">'+o.time+'</span></button>'
    +'<button class="fcard-chevbtn" onclick="toggleFcard(this)" title="Expand / collapse"><i data-lucide="chevron-right" class="fcard-chev"></i></button>'
    +'</div>'
    +'<div class="fcard-body">'+txRailHTML(o)+((subs&&subs.length)?subs.map(j=>txSubEntryHTML(MSGS[j],j)).join(''):'')+'</div></div>';}
  /* ND 6c: a NESTED subagent entry — a compact (~half-height) expandable trigger spanning the full rail width
     (the "overlay the rail cell" form — the cell isn't needed, and full-width signals the subagent is its own
     thing yet part of the agent), over the subagent's own rail body. The parent-id badge is gone (nesting
     conveys parentage); the sub-id badge leads, the state badge sits right of the preview (ND 6d), and the
     chevron keeps a square hit cell. */
  function txSubEntryHTML(o,j){const st=o.substate||'sb-active';
    return '<div data-comp="transcript-subentry" class="tx-sub" data-msgi="'+j+'">'
      +'<button class="tx-sub-trig" onclick="txSubToggle(event,this)" title="subagent '+o.sub+(o.subtype?' · '+o.subtype:'')+' — expand / collapse">'
      +'<span data-comp="subagent-badge" class="sbadge '+st+'">'+o.sub+'</span>'
      +'<span class="tx-sub-type">'+esc(o.subtype||'subagent')+'</span>'
      +'<span class="tx-sub-prev">'+o.body+'</span>'
      +(o.status?'<span data-comp="lifecycle-badge" class="dbadge db-'+o.status+'">'+({active:'Active',complete:'Complete',error:'Error'}[o.status]||'Complete')+'</span>':'')
      +'<span class="fcard-time">'+o.time+'</span>'
      +'<span class="tx-sub-chev"><i data-lucide="chevron-right" class="fcard-chev"></i></span></button>'
      +'<div class="tx-sub-body">'+txRailHTML(o)+'</div></div>';}
  function txSubToggle(e,btn){if(e&&e.stopPropagation)e.stopPropagation();const s=btn.closest('.tx-sub');if(s)s.classList.toggle('open');LU();}
  /* A7: contiguous rail panel. Top TITLE row holds the turn number (doc-title style) in its CONTENT; its rail box is
     EMPTY (no tag) and select-alls the whole message (mirrors Library's title rail). Then the primary prose ("txt"),
     then each typed block (think/read/…), each rail box carrying its 3-char type tag. */
  function txRailHTML(o){
    let rows='<div data-comp="message-rail-row" class="mrow mrow--title" data-mblk="title"><button class="mrail mrail--title" onclick="txWholeSel(event,this)" onmouseenter="txRailHover(this)" onmouseleave="txRailHoverOut(this)" title="Select the whole message"></button>'
      +'<div class="mrow-c"><div class="fcard-full"><span class="msg-turn">Turn '+(o.turn!=null?o.turn:'')+'</span></div></div></div>';
    rows+='<div data-comp="message-rail-row" class="mrow" data-mblk="text"><button class="mrail" onclick="txBlkSelMulti(event,this)" onmouseenter="txRailHover(this)" onmouseleave="txRailHoverOut(this)" title="Select this block (multi)">'+railTag('text')+'</button>'
      +'<div class="mrow-c"><div class="fcard-full">'+(o.full||o.body)+'</div></div></div>';
    if(o.blocks&&o.blocks.length){rows+=o.blocks.map(b=>'<div data-comp="message-rail-row" class="mrow" data-blk="'+b.k+'"><button class="mrail" onclick="txBlkSelMulti(event,this)" onmouseenter="txRailHover(this)" onmouseleave="txRailHoverOut(this)" title="Select this block (multi)">'+railTag(b.k)+'</button>'
      +'<div class="mrow-c">'+msgBlockHTML(b)+'</div></div>').join('');}
    return '<div class="mrail-wrap">'+rows+'</div>';}
  function clearTxBlkSel(){document.querySelectorAll('#tx-list .mrow.bsel').forEach(r=>r.classList.remove('bsel'));}
  function clearTxCardSel(){document.querySelectorAll('#tx-list .txcard.sel').forEach(c=>c.classList.remove('sel'));}
  /* A7 hover preview (mirrors Library railHover): a block rail lights its own row cream; the EMPTY title rail lights
     EVERY row cream (it select-alls). */
  function txRailHover(btn){const card=btn.closest('.txcard');if(!card)return;
    if(btn.classList.contains('mrail--title')){card.querySelectorAll('.mrow').forEach(r=>r.classList.add('hl'));}
    else{const row=btn.closest('.mrow');if(row)row.classList.add('hl');}}
  function txRailHoverOut(btn){const card=btn.closest('.txcard');if(card)card.querySelectorAll('.mrow.hl').forEach(r=>r.classList.remove('hl'));}
  /* A7 multi-select WITHIN a card (toggle); ONE card at a time → selecting a block clears other cards' selection AND
     the whole-card flag (a single block ≠ whole card). The .mrow.bsel set drives Embed/Attach. */
  function txBlkSelMulti(e,btn){if(e&&e.stopPropagation)e.stopPropagation();const row=btn.closest('.mrow');if(!row)return;const card=row.closest('.txcard');
    if(card){card.classList.remove('sel');const t=card.querySelector('.mrow--title');if(t)t.classList.remove('bsel');}
    document.querySelectorAll('#tx-list .mrow.bsel').forEach(r=>{if(r.closest('.txcard')!==card)r.classList.remove('bsel');});
    row.classList.toggle('bsel');eaUpdate('feed');}
  /* A7 whole-message select via the header OR the top title rail: toggle EVERY visible row in this card teal + flag the
     card .sel (→ Attach); ONE card at a time → clear other cards. */
  function txWholeSel(e,btn){if(e&&e.stopPropagation)e.stopPropagation();const card=btn.closest('.txcard');if(!card)return;
    document.querySelectorAll('#tx-list .mrow.bsel').forEach(r=>{if(r.closest('.txcard')!==card)r.classList.remove('bsel');});
    clearTxCardSel();
    const rows=[...card.querySelectorAll('.mrow')].filter(r=>r.style.display!=='none'&&!r.closest('.tx-sub'));   /* ND 6c: whole-message select = the parent message; nested subagent rows select individually */
    const all=rows.length&&rows.every(r=>r.classList.contains('bsel'));
    rows.forEach(r=>r.classList.toggle('bsel',!all));
    card.classList.toggle('sel',!all);
    eaUpdate('feed');}
  /* G2: generic select/deselect-all for the active feed tab (Messages whole-card+blocks · Scratch/Log/Inbox whole-card). */
  function feedSelectAll(btn){const tab=currentFeedTab();
    if(tab==='transcript'){clearTxBlkSel();const cards=[...document.querySelectorAll('#tx-list .txcard')].filter(c=>c.style.display!=='none');const allOn=cards.length&&cards.every(c=>c.classList.contains('sel'));
      cards.forEach(c=>{c.classList.toggle('sel',!allOn);const rows=[...c.querySelectorAll('.mrow')].filter(r=>r.style.display!=='none');rows.forEach(r=>r.classList.toggle('bsel',!allOn));});eaUpdate('feed');return;}
    const list=activeFeedList();if(!list)return;const cards=[...list.querySelectorAll('.fcard')].filter(c=>c.style.display!=='none');
    const allOn=cards.length&&cards.every(c=>c.classList.contains('sel'));cards.forEach(c=>c.classList.toggle('sel',!allOn));eaUpdate('feed');}
  /* A9: Scratch/Log/Inbox adopt the Messages card's selection model — header-click selects the WHOLE card (light
     teal) via msel-head; a separate chevron button toggles the dropdown (select ≠ expand); the card attaches via the
     shared Embed/Attach chip. NO checkbox, NO internal/sub-card selection (these cards have no sub-fields). */
  function fcardHTML(o){const a=AG[o.ag];return '<div data-comp="scratch-post" class="fcard" data-selcard>'
    +'<div class="fcard-head">'
    +'<button class="fcard-exp msel-head" onclick="fcardSel(event,this)" title="Select this card (Attach)">'
    +(o.status?'<span data-comp="lifecycle-badge" class="dbadge db-'+o.status+'">'+({active:'Active',complete:'Complete',error:'Error'}[o.status]||'Complete')+'</span>':'')
    +badgeHTML(a)
    +'<span class="fcard-prev">'+o.body+'</span><span class="fcard-time">'+o.time+'</span></button>'
    +'<button class="fcard-chevbtn" onclick="toggleFcard(this)" title="Expand / collapse"><i data-lucide="chevron-right" class="fcard-chev"></i></button>'
    +'</div>'
    +'<div class="fcard-body"><div class="fcard-full">'+(o.full||o.body)+'</div>'+msgBlocksHTML(o)+'</div></div>';}
  function logCardHTML(o){const a=AG[o.ag]||AG.user;return '<div data-comp="log-line" class="fcard" data-selcard>'
    +'<div class="fcard-head">'
    +'<button class="fcard-exp msel-head" onclick="fcardSel(event,this)" title="Select this card (Attach)">'+badgeHTML(a)
    +'<span class="fcard-prev fcard-log"'+(o.warn?' style="color:var(--warning)"':'')+'>'+o.txt+'</span><span class="fcard-time">'+o.time+'</span></button>'
    +'<button class="fcard-chevbtn" onclick="toggleFcard(this)" title="Expand / collapse"><i data-lucide="chevron-right" class="fcard-chev"></i></button>'
    +'</div>'
    +'<div class="fcard-body"><div class="fcard-full fcard-log">'+a.name+' · '+o.txt+(o.warn?' · awaiting your input':'')+'</div></div></div>';}
  /* A9: whole-card select (teal) for Scratch/Log/Inbox — multi-select, drives the shared Copy + Embed/Attach strip */
  function fcardSel(e,btn){if(e&&e.stopPropagation)e.stopPropagation();const c=btn.closest('.fcard');if(c)c.classList.toggle('sel');eaUpdate(c&&c.closest('#hist-list')?'hist':'feed');}
  function miniBadges(keys,cap){cap=cap||2;let h=keys.slice(0,cap).map(k=>badgeXsHTML(AG[k])).join('');if(keys.length>cap)h+='<span class="rcpt-more" title="'+esc(keys.slice(cap).join(', '))+'">+'+(keys.length-cap)+'</span>';return h;}   /* ND 5c: the History receiver badges take the SMALL tier (+N overflow in the recipient form), matched with the Transcript recipients */
  /* I1/I2/I3: History adopts the feed-card model — header-click selects (light-teal), a separate flush chevron expands;
     EDIT is a header ghost button (after the attach tags, before the timestamp). The select region (.fcard-exp) holds
     only NON-interactive content; Edit/time/chevron are SIBLINGS in .fcard-head (a <button> can't nest in a <button>). */
  function histCardHTML(o,i){const a=AG[o.from];return '<div data-comp="history-card" class="fcard'+(o.sel?' sel open':'')+'" data-histcard'+(typeof i==='number'?' data-hidx="'+i+'"':'')+'>'
    +'<div class="fcard-head">'
    +'<button class="fcard-exp msel-head" onclick="fcardSel(event,this)" title="Select this prompt">'
    +'<span data-comp="lifecycle-badge" class="dbadge '+o.badge+'">'+o.status+'</span>'+badgeHTML(a)
    +'<i data-lucide="arrow-right" style="width:var(--size-12);height:var(--size-12);color:var(--muted);flex:0 0 auto"></i>'+miniBadges(o.to,2)
    +'<span class="flex-1"></span>'+attTrigHTML(o)+'</button>'
    +'<button data-comp="ghost-icon-button" class="ghost-ic" onclick="event.stopPropagation();histAct(\'edit\')" title="Edit in Compose"><i data-lucide="square-pen"></i></button>'
    /* Next-up item 5: prompts that haven't run yet (status not Active/Complete — Queued/Next/Held) carry a
       danger trash ghost right after Edit, so a prompt can be deleted before it ever runs. */
    +(o.badge!=='db-active'&&o.badge!=='db-complete'?'<button data-comp="ghost-icon-button" class="ghost-ic ghost-ic--danger" onclick="event.stopPropagation();histDelete(this)" title="Delete prompt (not yet run)"><i data-lucide="trash-2"></i></button>':'')
    +'<span class="fcard-time">'+o.time+'</span>'
    +'<button class="fcard-chevbtn" onclick="toggleFcard(this)" title="Expand / collapse"><i data-lucide="chevron-right" class="fcard-chev"></i></button>'
    +'</div>'
    +attPopHTML(o)
    +'<div class="fcard-body"><div class="fcard-full">'+o.body+'</div></div></div>';}
  /* v1.2: attachments on History cards — a count chip in the header opens a popover; each entry opens the
     item in the Library (images → Assets, docs → Documents). History-only for now; built to reuse later. */
  function attTrigHTML(o){if(!o.att||!o.att.length)return '';const n=o.att.length;
    return '<span data-comp="attachment-count-chip" data-status="planned" class="att-chip" onclick="event.stopPropagation();toggleAttPop(this)" title="'+n+' attachment'+(n>1?'s':'')+'"><i data-lucide="paperclip"></i><span class="att-n">'+n+'</span></span>';}
  function attPopHTML(o){if(!o.att||!o.att.length)return '';const n=o.att.length;
    const items=o.att.map(at=>{const asset=at.type==='asset';const tab=asset?'assets':'documents';const ic=asset?'image':'file-text';
      return '<button data-status="planned" type="button" class="att-item" onclick="openAttachment(event,\''+tab+'\')"><i data-lucide="'+ic+'" class="att-ic"></i><span class="att-name">'+esc(at.name)+'</span><i data-lucide="arrow-up-right" class="att-go"></i></button>';}).join('');
    return '<div class="att-pop"><div class="att-pop-head">'+n+' attachment'+(n>1?'s':'')+'</div>'+items+'</div>';}
  function toggleAttPop(trig){const card=trig.closest('.fcard');if(!card)return;const pop=card.querySelector('.att-pop');if(!pop)return;
    const open=pop.classList.contains('open');closeAllPopups();if(!open){pop.classList.add('open');card.classList.add('att-open');LU();}}
  function openAttachment(e,tab){e.stopPropagation();closeAllPopups();switchTab('doc',tab);toast('Opening attachment in Library → '+(tab==='assets'?'Assets':'Documents'));}
  /* Messages carry typed content blocks keyed to the Content toggles (Text/Thoughts/Read/Write/Bash/Diffs/Meta),
     so the toggles have real content to filter. A block's data-blk = its kind; the main reply text has no blocks
     entry — it's every card's `text` row (next-up item 4). One card is an agent→agent relay. */
  const MSGS=[
    {ag:'sandy',dir:'in',status:'active',turn:8,time:'14:41',body:`Fanned out six explorers across the auth surface — JWT middleware, session store, token rotation — to map every validateToken() path in parallel. Aggregating their findings into the vulnerability report now.`,
     blocks:[
       {k:'think',t:'The refresh path reissues the session cookie but carries the CSRF secret over unchanged — a privilege-boundary smell worth probing before I write this up.'},
       {k:'read',t:'● Read  src/auth/session.ts (212 lines)'},
       {k:'search',t:'● Grep  "refreshToken" in src/auth\n  ⎿ 6 matches across session.ts, tokens.ts'}]},
    /* Multi-subagent stream, demo 1 of 2 — researcher-01-sandy's full run-A fan-out (A1–A6, matching sandy's Team-Graph roster: 3 Explore active · 1 general-purpose done · 1 code-reviewer active · 1 general-purpose error). The full multi-subagent stream is split across TWO different agents (sandy here, fen below), not two runs on one agent, so each fits the timespan of its example card. ND 6c: these entries render NESTED inside their parent's card — the old "subagent of …" meta blocks are gone (nesting conveys parentage). */
    {ag:'sandy',sub:'A1',subtype:'Explore',substate:'sb-active',dir:'in',status:'active',turn:8,time:'14:41',body:`JWT middleware mapped — 7 validateToken() call-sites; session.ts:142 is the one refresh path that skips the exp check.`,
     blocks:[
       {k:'read',t:'● Read  src/auth/middleware/jwt.ts (164 lines)'}]},
    {ag:'sandy',sub:'A2',subtype:'Explore',substate:'sb-active',dir:'in',status:'active',turn:8,time:'14:41',body:`Session store swept — the refresh handler reissues the cookie without re-checking expiry, so a held refresh token renews indefinitely.`,
     blocks:[
       {k:'search',t:'● Grep  "refresh" in src/auth/session.ts\n  ⎿ 4 matches (reissue path at :88)'}]},
    {ag:'sandy',sub:'A3',subtype:'Explore',substate:'sb-active',dir:'in',status:'active',turn:8,time:'14:41',body:`Token-rotation path traced — no sliding window on the refresh secret; rotation reuses the same signing key across sessions.`,
     blocks:[
       {k:'read',t:'● Read  src/auth/tokens.ts (88 lines)'}]},
    {ag:'sandy',sub:'A4',subtype:'general-purpose',substate:'sb-idle',dir:'in',status:'complete',turn:8,time:'14:41',body:`Cross-checked the three findings against the OWASP JWT cheatsheet — all map to known weaknesses; handing the summary back to sandy.`},
    {ag:'sandy',sub:'A5',subtype:'code-reviewer',substate:'sb-active',dir:'in',status:'active',turn:8,time:'14:41',body:`Reviewing the exp-enforcement approach — the fix belongs inside validateToken() itself, not the caller, or the bypass reopens on the next refresh path.`,
     blocks:[
       {k:'read',t:'● Read  src/auth/session.ts · tokens.ts'}]},
    {ag:'sandy',sub:'A6',subtype:'general-purpose',substate:'sb-error',dir:'in',status:'error',turn:8,time:'14:41',body:`Run failed — couldn't reach the staging auth service to confirm the bypass live (ECONNREFUSED). The static findings still stand.`,
     blocks:[
       {k:'bash',t:'● Bash  curl -s https://staging.internal/auth/health\n  ⎿ Error: connect ECONNREFUSED 10.0.3.12:8443 · exit 1'}]},
    {ag:'user',dir:'out',recipients:['sandy','drew'],turn:9,time:'14:42',body:`Confirm the expiry bypass with auditor-01 and draft a remediation plan to the scratchpad.`},   /* a user send carries its To/Target selection as recipients[] (multi) — drives the → recipient mini-badges; the rest default to [user] */
    {ag:'drew',dir:'in',status:'complete',turn:11,time:'14:43',body:`Confirmed 2 of 3 vulns. Expiry bypass is critical — tokens refresh indefinitely. Demoted "no rate limiting" to medium; it's behind the gateway throttle.`,
     blocks:[
       {k:'read',t:'● Read  src/auth/tokens.ts (88 lines)'},
       {k:'think',t:'The rate-limit finding is already covered by the gateway throttle — demote it to medium and keep the focus on the expiry bypass.'}]},
    {ag:'vega',dir:'in',status:'complete',turn:12,time:'14:44',body:`Reviewed the patch diff. Two style nits and one missing test for the rotation path before this can merge.`,
     blocks:[
       {k:'diff',t:'  function validateToken(token) {\n-   return decode(token)\n+   const c = decode(token)\n+   if (c.exp < now()) throw new TokenExpired()\n+   return c\n  }'}]},
    {ag:'kai',dir:'in',status:'complete',turn:14,time:'14:45',body:`Synthesizing findings into a remediation plan: critical → high → medium, each with an owner and a checklist. Writing it to the shared scratchpad now.`,
     blocks:[
       {k:'write',t:'● Write  <project>/.awl/scratchpad.md (+18 −0)'}]},   /* scratchpad lives with the project (.awl/) */
    {ag:'sandy',dir:'in',status:'complete',turn:15,time:'14:46',body:`Patch is ready on the rotation branch — can you re-check the expiry path holds under token reuse?`,
     blocks:[
       {k:'meta',t:'relayed via link from coder-01-max · trigger: Next'}]},
    /* Multi-subagent stream, demo 2 of 2 — scribe-01-fen's run-B helpers (B1–B3, matching fen's Team-Graph roster: code-reviewer done · Explore active · general-purpose error). fen's card also carries an A and a C run; only run B is streamed here so the example fits one card's timespan (the companion 6-subagent fan-out is demo 1 on sandy, above). */
    {ag:'fen',dir:'in',status:'active',turn:6,time:'14:46',body:`Compiling the auth-fix changelog — dispatched a review + exploration pass over the rotation patch so the writeup cites the exact call-sites and carries the reviewer's verdict.`,
     blocks:[
       {k:'workflow',t:'▸ Workflow changelog-sweep — phase Verify · 2/3 agents complete · review + call-site pass over the rotation patch'},
       {k:'write',t:'● Write  docs/CHANGELOG.md (+12 −0)'},
       {k:'read',t:'● Read  src/auth/tokens.ts (88 lines)'}]},
    {ag:'fen',sub:'B1',subtype:'code-reviewer',substate:'sb-idle',dir:'in',status:'complete',turn:6,time:'14:46',body:`Reviewed the rotation patch for the changelog — the exp check now gates every refresh; verdict Approve with one note on the flaky timing test.`},
    {ag:'fen',sub:'B2',subtype:'Explore',substate:'sb-active',dir:'in',status:'active',turn:6,time:'14:46',body:`Pulling the exact call-sites for the writeup — validateToken() is touched in three files; session.ts:142 is the line the fix closes.`,
     blocks:[
       {k:'read',t:'● Read  src/auth/session.ts · middleware/jwt.ts'}]},
    {ag:'fen',sub:'B3',subtype:'general-purpose',substate:'sb-error',dir:'in',status:'error',turn:6,time:'14:46',body:`Run failed — tried to render the changelog diff against the staging docs but the docs service timed out. Retrying once it's reachable.`,
     blocks:[
       {k:'bash',t:'● Bash  make docs-preview\n  ⎿ Error: gateway timeout after 30s · exit 1'}]},
    {ag:'max',dir:'in',status:'active',turn:17,time:'14:47',body:`Patched validateToken() to enforce exp and added refresh-token rotation. Vitest suite green except one flaky timing case I'm isolating.`,
     blocks:[
       {k:'bash',t:'● Bash  pnpm vitest run auth\n  ⎿ 41 passed · 1 flaky (rotation timing)'},
       {k:'diff',t:'+ rotateRefresh(token, { window: 30_000 })'},
       {k:'write',t:'● Write  src/auth/tokens.ts (+24 −6)'}]},
    /* subagent events nest INSIDE their parent's card (here, coder-01-max) — ND 6c. Always Received (helpers only ever talk to their parent, never the user); sub = the group+member id, subtype = the agent type. */
    {ag:'max',sub:'A1',subtype:'Explore',substate:'sb-active',dir:'in',status:'active',turn:17,time:'14:47',body:`Mapped 7 validateToken() call-sites; session.ts:142 is the one refresh path that skips the exp check — that's the bypass max is patching.`,
     blocks:[
       {k:'read',t:'● Read  src/auth/session.ts · tokens.ts · middleware/jwt.ts'}]},
    {ag:'drew',dir:'in',status:'error',turn:18,time:'14:48',body:`Run failed — the staging smoke test errored before the expiry assertion: the rotation branch can't reach the auth service (ECONNREFUSED). Re-run once staging is back up.`,
     blocks:[
       {k:'bash',t:'● Bash  pnpm test:smoke --env staging\n  ⎿ Error: connect ECONNREFUSED 10.0.3.12:8443 · exit 1'},
       {k:'meta',t:'auto-stop: run ended on error · 0 retries left'}]}
  ];
  const SCRATCH=[
    {ag:'sandy',time:'14:33:07',body:`Posted finding: <b class="text-foreground">Token Expiry Bypass (CRITICAL)</b> — validateToken() accepts expired tokens; refresh issues new tokens indefinitely.`},
    {ag:'drew',time:'14:37:18',body:`Confirmed CRITICAL + HIGH. Demoted "no rate limiting" to MEDIUM — endpoint sits behind the gateway throttle.`},
    {ag:'kai',time:'14:40:36',body:`Wrote <b class="text-foreground"># Auth Remediation Plan</b> — Critical → High → Medium with owners + checklist. Ready for approval.`}
  ];
  const LOG=[
    {time:'14:31:58',ag:'user',txt:'dispatched researcher-01-sandy'},
    {time:'14:32:04',ag:'sandy',txt:'started'},
    {time:'14:33:07',ag:'sandy',txt:'posted scratch (CRITICAL)'},
    {time:'14:35:09',ag:'sandy',txt:'→ synthesizer-01 link fired'},
    {time:'14:35:53',ag:'kai',txt:'committed 3f2a1b'},
    {time:'14:37:18',ag:'drew',txt:'flagged 2 findings'},
    {time:'14:38:30',ag:'drew',txt:'permission request',warn:true},
    {time:'14:41:12',ag:'sandy',txt:'approval request',warn:true},
    {time:'14:43:33',ag:'sage',txt:'deploy gate held'},
    {time:'14:50:12',ag:'system',txt:'tmux bridge unreachable — reconnecting',warn:true}   /* Next-up item 15: a system event carries the reserved System badge (logCardHTML reads AG.system) */
  ];
  const HIST=[
    {badge:'db-active',status:'Active',from:'user',to:['kai','drew'],time:'14:41',sel:true,att:[{name:'jwt-expiry-trace.png',type:'asset'},{name:'CLAUDE.md',type:'doc'}],body:`Re-run the auth test suite against the rotation branch and confirm the expiry-bypass path is closed under token reuse.`},
    {badge:'db-queued',status:'Queued',from:'user',to:['max'],time:'14:39',body:`Once the rotation patch lands, open a PR with the changelog entry and request review from reviewer-01.`},
    {badge:'db-next',status:'Next',from:'user',to:['drew'],time:'14:38',body:`After the audit confirms, write up each finding with CVSS scores and a suggested fix owner.`},
    {badge:'db-held',status:'Held',from:'user',to:['sage'],time:'14:36',body:`Hold the production deploy until the expiry fix is merged and the smoke tests pass on staging.`},
    {badge:'db-complete',status:'Complete',from:'kai',to:['max'],time:'14:30',att:[{name:'auth-token-rotation-shimmering-falcon.md',type:'doc'}],body:`Relay: apply the sliding-window rotation in validateToken() and keep the change behind a feature flag.`}
  ];
  function renderFeed(){
    /* ND 6c: subagent entries no longer render as top-level cards — each parent card collects the contiguous
       run of `sub` entries that follow it in MSGS (communication order) and nests them inside its body. */
    const m=document.getElementById('tx-list');if(m){let html='';
      for(let i=0;i<MSGS.length;i++){const o=MSGS[i];if(o.sub)continue;
        const subs=[];let j=i+1;while(j<MSGS.length&&MSGS[j].sub&&MSGS[j].ag===o.ag){subs.push(j);j++;}
        html+=txCardHTML(o,i,subs);}
      m.innerHTML=html;applyTxFilters();}
    const s=document.getElementById('scratch-list');if(s)s.innerHTML=SCRATCH.map(fcardHTML).join('');
    const l=document.getElementById('log-list');if(l)l.innerHTML=LOG.map(logCardHTML).join('');
    const h=document.getElementById('hist-list');if(h){h.innerHTML=HIST.map(histCardHTML).join('');if(typeof applyHistFilters==='function')applyHistFilters();}   /* item 9: re-apply the History-From filter on re-render */
    renderInbox();}
  /* D (JUMP): on expand, attach a jump pill to the card body (idempotent) so a long body that overflows its
     capped max-height gets the scroll-to-end pill; jumpUpdate primes its show/hide + position immediately. */
  function toggleFcard(btn){const c=btn.closest('.fcard');if(!c)return LU();c.classList.toggle('open');
    if(c.classList.contains('open')){const b=c.querySelector('.fcard-body');if(b){attachJump(b);jumpUpdate(b);}}LU();}
  /* Export (Copy / Export-to-file) for the merged control's feed + History hosts — selection-only: copy the selected
     card(s) to the clipboard, or export them → a new Library → Documents doc via createDoc (R-batch items 6 + 8).
     Cut was removed in the consolidation (item 6). */
  function cardText(c){
    /* a Messages card's body is the contiguous rail (title + message + blocks), so gather every row's content —
       grabbing only the first .fcard-full would capture just the "Turn N" title. Other feed/history cards have a
       single body block. (Used by Copy selected + Embed/Attach + the Export selected → file content.) */
    if(c.classList.contains('txcard')){const rows=[...c.querySelectorAll('.mrow-c')].filter(r=>!r.closest('.tx-sub')).map(r=>r.textContent.trim()).filter(Boolean);if(rows.length)return rows.join('\n');}   /* ND 6c: a parent card's text excludes its nested subagent entries */
    const b=c.querySelector('.fcard-full,.inbox-detail,.rc-body');return b?b.textContent.trim():'';}
  function toggleExport(btn){if(btn.disabled)return;const wrap=btn.closest('.exp');if(!wrap)return;const open=wrap.classList.contains('open');closeAllPopups();if(!open){wrap.classList.add('open');const pc=btn.closest('.plan-card');if(pc)pc.classList.add('pop-open');}}   /* R11 item 5: in a plan footer, release the plan-card clip too (harmless elsewhere — closest('.plan-card') is null in feed/hist/doc) */
  /* (R-batch item 6: the separate expGate() that gated #feed-exp / #hist-exp is gone — the merged control's single
     trigger is gated by eaUpdate(host), which folds in copy/file/embed/attach.) */
  function feedExport(mode){closeAllPopups();
    const list=activeFeedList();const tab=currentFeedTab();
    const cards=list?[...list.querySelectorAll('.fcard.sel')]:[];   /* selection-only */
    if(!cards.length){toast('Select cards first');return;}
    const txt=cards.map(cardText).filter(Boolean).join('\n\n');
    if(mode==='copy-sel'){if(navigator.clipboard)navigator.clipboard.writeText(txt).catch(()=>{});
      toast('Copied '+cards.length+' '+tab+' card'+(cards.length>1?'s':''));return;}
    if(mode==='file-sel'){const n=cards.length;const fname=tab+'-export-'+(new Date().toTimeString().slice(0,5).replace(':',''))+'.md';
      addDocPaste(txt,fname);   /* R-batch item 8: route to Library → Documents + the Add-document (Paste) workflow with the selection content */
      toast('Exported '+n+' '+tab+' card'+(n>1?'s':'')+' → Documents · '+fname);return;}}
  /* v1.x #7: the summary overlay is shared by Messages · Scratch · Log — each tab gets its own mock summary,
     title and count. The Messages body is captured once from its static HTML so it stays single-sourced. */
  let TX_SUMMARY_BODY='';
  const FEED_SUMMARIES={
    transcript:{title:'Conversation summary',
      sub:()=>{const sel=document.querySelectorAll('#tx-list .fcard.sel').length;return sel?sel+' selected messages':'all '+MSGS.length+' messages';},
      body:()=>TX_SUMMARY_BODY},
    scratch:{title:'Scratchpad summary',
      sub:()=>'all '+SCRATCH.length+' scratch posts',
      body:()=>`<h4>Shared scratchpad — auth remediation</h4>
        <p><b class="k">researcher-01-sandy</b> posted the headline finding: a <b>critical</b> token-expiry bypass — <code>validateToken()</code> accepts expired tokens and refresh reissues them indefinitely.</p>
        <h5>Triage</h5>
        <ul>
          <li><b class="k">auditor-01-drew</b> confirmed the Critical + High; demoted "no rate limiting" to Medium (behind the gateway throttle).</li>
          <li><b class="k">synthesizer-01-kai</b> wrote <code># Auth Remediation Plan</code> — Critical → High → Medium with owners + a checklist, ready for approval.</li>
        </ul>
        <p class="fo-sub">Generated from all 3 scratch posts · mock summary</p>`},
    log:{title:'Activity-log summary',
      sub:()=>'all '+LOG.length+' log entries',
      body:()=>`<h4>Activity log — last ~12 min</h4>
        <p>The run kicked off at <b>14:31</b> when <b class="k">you</b> dispatched <b class="k">researcher-01-sandy</b>; the thread fanned out to the auditor, synthesizer, and a deploy gate.</p>
        <h5>Highlights</h5>
        <ul>
          <li><b class="k">sandy</b> started, posted a CRITICAL scratch finding, and fired a link to <b class="k">synthesizer-01</b>; <b class="k">kai</b> committed <code>3f2a1b</code>.</li>
          <li><b class="k">drew</b> flagged 2 findings.</li>
        </ul>
        <h5>Needs you</h5>
        <ul>
          <li>6 open Inbox requests — <b class="k">drew</b> error — staging unreachable (14:48), <b class="k">rowan</b> warning — max turns reached, paused (14:46), <b class="k">sage</b> permission (deploy gate, 14:43), <b class="k">sandy</b> plan to merge (14:41) + permission to edit settings.json (14:42), and <b class="k">vega</b> decision on rotation strategy (14:44).</li>
        </ul>
        <p class="fo-sub">Generated from all 9 log entries · mock summary</p>`}
  };
  function currentFeedTab(){const b=document.querySelector('[data-tab-group="feed"].tab-btn.active');return b?b.dataset.tab:'transcript';}
  function toggleSummary(){const ov=document.getElementById('feed-summary');if(!ov)return;
    if(!TX_SUMMARY_BODY){TX_SUMMARY_BODY=(document.getElementById('fo-body')||{}).innerHTML||'';}   /* grab the static Messages summary once, before any injection */
    const open=ov.classList.toggle('open');const btn=document.getElementById('summary-btn');if(btn)btn.classList.toggle('active',open);
    if(open){const s=FEED_SUMMARIES[currentFeedTab()]||FEED_SUMMARIES.transcript;
      const ti=document.querySelector('#feed-summary .fo-title');if(ti)ti.innerHTML='<i data-lucide="sparkles"></i>'+s.title;
      const c=document.getElementById('fo-count');if(c)c.textContent=s.sub();
      const bd=document.getElementById('fo-body');if(bd)bd.innerHTML=s.body();}
    LU();}

  /* ===== Inbox (approvals you owe) — data-driven (REQS), expandable + selectable like Log =====
     v10p1 #15: each card collapses to identity + type badge + title; expand reveals the detail + actions.
     The checkbox multi-selects (shared Copy/Share strip). data-agent lets a Pending badge jump-expand it.
     #11: Reject + Deny use the danger color; Approve stays pink-primary. Permission is binary Approve/Deny (+Reply) — "Always allow" fully removed. */
  /* P2: Inbox grouped into typed SECTIONS — Error · Warning · Permission · Plan · Decision · Response. The
     section header carries the type label, so cards drop the per-card type badge (this supersedes the old
     reddish→copper attention ramp). Approval → Plan. Decision is the AskUserQuestion surface — one question
     per card. Plan cards keep only Review (→ Plans tab) + Reply; approval + agent verdicts live in the Plans
     tab. Next-up item 14: RESPONSE is the lone NON-blocking, non-request section, at the BOTTOM of the ramp
     (neutral --muted heading like Plan/Decision) — a run ended with output the user hasn't reviewed: the
     answer to the operator's prompt (the five sections above are agent REQUESTS of you). ONE coalesced card
     per agent — a second unseen run UPDATES the card (the ×N runs marker), never stacks. It opens on run end,
     stays open (coalescing) if a new prompt fires unseen, and clears on Retire/Delete. The status badge stays
     plain idle (no fifth state, no state-dependent click) while the node-inbox envelope counts it like a
     Warning. View / Reply each COMPLETE the item — no Dismiss, no read-tracking ("leaves only when completed,
     never on a glance"). */
  const INBOX_SECTIONS=[
    {type:'error',lab:'Error'},
    {type:'warning',lab:'Warning'},
    {type:'permission',lab:'Permission'},
    {type:'plan',lab:'Review'},   /* ND 16: renamed from "Plans & Docs" — one review section covering plans, doc hand-offs (doc-* ids route to the Documents tab), AND workflow approvals (entries carrying a wf payload) */
    {type:'decision',lab:'Decision'},
    {type:'response',lab:'Response'}
  ];
  function secLabel(t){const s=INBOX_SECTIONS.find(x=>x.type===t);return s?s.lab:t;}
  const REQS=[
    {ag:'sage',type:'permission',time:'14:43',title:'Run bash command',cmd:'kubectl apply -f deploy/prod.yaml'},
    {ag:'sandy',type:'plan',time:'14:41',title:'Merge remediation plan to main',body:'Plan: Auth token-rotation remediation · 3 files · +84 −19 · rotation path covered by new test',plan:'plan-1'},
    {ag:'wren',type:'plan',time:'14:45',title:'Review README.md edits before commit',body:'Docs edit: README.md · +37 −12 · refreshed the Quick-start and the driver-seam overview to match the sidecar rename — ready for a look before it lands.',plan:'doc-readme'},   /* doc-review flow (Lane I): SAME unified plan card, plan id is doc-* so Review routes to Library → Documents (the doc card lands after the Lane-L Plans+Documents merge; graceful no-op until then) */
    {ag:'lex',type:'plan',time:'14:53',title:'Run workflow: design-verify-sweep',wf:{name:'design-verify-sweep',desc:'Drive every touched design component headed — one verifier per panel, findings adversarially checked before they report.',phases:['Scan','Verify','Report'],script:"export const meta = {\n  name: 'design-verify-sweep',\n  description: 'Verify the touched design components headed',\n  phases: [\n    { title: 'Scan',   detail: 'list the touched components' },\n    { title: 'Verify', detail: 'one headed verifier per panel' },\n    { title: 'Report', detail: 'adversarial check, then summarize' },\n  ],\n}\nphase('Scan')\nconst targets = await agent('List the design components this diff touches.', {schema: LIST})\nphase('Verify')\nconst runs = await parallel(targets.map(t => () =>\n  agent('Drive ' + t + ' headed at both width extremes; screenshot each state.', {schema: RUN})))\nphase('Report')\nreturn await agent('Adversarially verify the findings, then summarize.', {schema: REPORT})"}},   /* ND 16: a /workflows approval routed through the Inbox — the PreToolUse interception is spike-proven; the preview renders in the card content, and the card carries its OWN Approve/Reject round-trip (a workflow has no Library home, so its approval lives on the card — see DESIGN.md → The Inbox tab) */
    {ag:'sandy',type:'permission',time:'14:42',title:'Edit settings.json',cmd:'apply patch → .claude/settings.json (add rotation-hook allow rule)'},
    {ag:'vega',type:'decision',time:'14:44',title:'Choose token rotation strategy',options:[
      {nm:'A · Sliding window',desc:'Refresh extends expiry; simplest, slightly weaker on replay.'},
      {nm:'B · One-time rotation',desc:'Each refresh invalidates the prior token; strongest, more churn.'}]},
    {ag:'drew',type:'error',subtype:'Connection',time:'14:48',title:'Staging smoke test unreachable',body:`Run failed — the staging smoke test errored before the expiry assertion: the rotation branch can't reach the auth service (ECONNREFUSED 10.0.3.12:8443 · exit 1). Re-run once staging is back up.`,cmd:'pnpm test:smoke --env staging'},   /* wired from the Messages status:'error' drew/ECONNREFUSED card → the agent-card→Inbox path */
    {ag:'rowan',type:'warning',subtype:'Max turns',time:'14:46',title:'Max turns reached — run paused at the limit',body:`rowan hit its Max-turns auto-stop limit (50 / 50 turns) and paused mid-task — a notify-only heads-up (it never auto-kills). Dismiss to clear it from the Inbox, or Reply to weigh in.`},   /* Warning simplification: a Warning is a plain FYI — Dismiss (pink, the completion action) + Reply only; the old cap-specific Continue/Raise cap/Stop set is gone (no per-warning dependency). subtype 'Max turns' drives the --warning header badge. Warning = attention-needed, not a hard block: a --warning heading + badge, no danger card edge (Error keeps the single alarm edge). */
    {ag:'max',type:'warning',subtype:'Context 82%',time:'14:52',title:'Nearing the context limit — compaction imminent',body:`max is at ~82% of its context window; an auto-compaction will trigger soon. No hard block — a heads-up while the run keeps going. Dismiss to clear it, or Reply to weigh in.`},   /* warning-model + inbox-footer demo: a NON-blocking warning on an ACTIVE agent (max's graph card stays Active) — the case the per-card inbox footer exists for: an open item that doesn't flip the binary status badge. Its footer envelope shows a count while the badge reads active. */
    {ag:'system',type:'error',subtype:'Infrastructure',time:'14:50',title:'tmux bridge unreachable — agent control suspended',body:`The sidecar lost the tmux/WSL2 bridge (connect timeout after 3 retries) — run control, sends, and reads are suspended fleet-wide until the bridge is back. One System card stands in for 13 identical per-agent errors.`,cmd:'wsl.exe -d Ubuntu -- tmux ls'},   /* Next-up item 15: a SYSTEM-WIDE failure fronts the reserved System identity (infrastructure / account-level / shared services). Reply renders DISABLED — greyed, not removed (the Export-menu convention): System is never addressable. No graph card exists, so there's no node-inbox envelope mirror. */
    {ag:'kai',type:'response',time:'14:49',runs:2,title:'Run ended — final reply not yet reviewed',body:`kai's last 2 runs ended with replies you haven't reviewed — latest: the remediation-plan synthesis (Turn 14). View jumps to the run's final reply in Messages, scoped to kai; Reply quotes it in the Editor. Either completes this item; it also clears on Retire/Delete — never on a glance.`}   /* Next-up item 14: the Response demo — kai's graph card stays plain IDLE (no fifth badge state) while his node-inbox envelope counts this like a Warning. runs:2 = two unseen runs COALESCED into the one card (the ×2 runs marker), never stacked. */
  ];
  function inboxReplyHTML(dis){return '<button data-comp="button" class="btn-secondary btn-sm ml-auto"'+(dis?' disabled':'')+' onclick="inboxReply(this)" title="'+(dis?'Reply is unavailable — System isn\'t addressable':'Reply via the Editor (quotes the request as a reference block)')+'"><i data-lucide="send-horizontal" class="w-3 h-3"></i>Reply</button>';}   /* Reply = teal hand-off → the Editor, pre-filled with a frozen embed block of this card + the agent pre-targeted. R11 item 2: the old 2px navy divider before Reply was dropped; ml-auto on the button preserves its right-alignment. Item 15: dis=true on a System Error card — DISABLED, greyed not removed (the Export-menu convention). */
  function inboxCardHTML(o,i){const a=AG[o.ag];let detail,acts;
    if(o.type==='permission'){detail='<div class="rc-body" style="font-family:var(--font-mono)">'+esc(o.cmd)+'</div>';
      acts='<button data-comp="button" class="btn-main btn-sm" onclick="inboxResolve(this,\'Approved\')">Approve</button><button data-comp="button" class="btn-danger btn-sm" onclick="inboxResolve(this,\'Denied\')">Deny</button>'+inboxReplyHTML();}   /* binary Approve/Deny (+Reply) — "Always allow" fully removed (no always-allow rule-persistence, now or later) */
    else if(o.type==='plan'){
      /* ND 16: the Review section covers plans, doc hand-offs, AND workflow approvals — a wf entry renders the
         workflow preview (name / description / phase chips / full script) in the card content. Unlike plan/doc
         cards it carries the Approve/Reject ROUND-TRIP on the card (allow = launch · deny = abort — a workflow
         has no Library home, so its approval lives here) plus Review (planned — reuses the Library editor) + Reply. */
      if(o.wf){detail='<div class="wf-prev"><div class="rc-body"><b>'+esc(o.wf.name)+'</b></div><div class="wf-desc">'+esc(o.wf.desc)+'</div>'
          +'<div class="wf-phases">'+(o.wf.phases||[]).map(p=>'<span data-comp="workflow-phase-chip" class="wf-phase">'+esc(p)+'</span>').join('')+'</div>'
          +'<pre class="wf-script">'+esc(o.wf.script||'')+'</pre>'
          /* the round-trip's resolved states (shown via the card's approved/rejected classes — wfResolve): the
             hook verdict either LAUNCHES the workflow (allow) or ABORTS the tool call before launch (deny) */
          +'<div class="wf-resolved wf-resolved--ok"><i data-lucide="circle-check"></i>Approved — workflow launched</div>'
          +'<div class="wf-resolved wf-resolved--no"><i data-lucide="circle-x"></i>Rejected — workflow aborted before launch</div></div>';
        /* Approve/Reject ROUND-TRIP: unlike plan/doc cards (whose approval lives in the Library), a workflow has
           no Library home — its approval lives ON the card. Approve = the hook allows the tool call (launch);
           Reject = the hook denies it (abort). Review (planned) will reuse the shared Library editor. */
        acts='<button data-comp="button" class="btn-main btn-sm" onclick="wfResolve(this,true)" title="Approve — allow the Workflow tool call; the workflow launches">Approve</button>'
          +'<button data-comp="button" class="btn-danger btn-sm" onclick="wfResolve(this,false)" title="Reject — deny the tool call; the workflow never launches">Reject</button>'
          +'<button data-comp="button" data-status="planned" class="btn btn-sm" onclick="toast(\'Open the workflow in the Library editor — planned\')" title="Review the workflow in the Library editor (planned — reuses the shared editor)"><i data-lucide="file-text" class="w-3 h-3"></i>Review</button>'+inboxReplyHTML();}
      else{detail='<div class="rc-body">'+esc(o.body)+'</div>';   /* plans + docs: Review (→ the matching Library tab) + Reply only — no Approve/Reject */
        const isDoc=o.plan&&o.plan.indexOf('doc-')===0;
        acts='<button data-comp="button" class="btn btn-sm" onclick="reviewPlan(\''+o.plan+'\')" title="'+(isDoc?'Review the full doc in Library → Documents':'Review the full plan in Library → Plans')+'"><i data-lucide="file-text" class="w-3 h-3"></i>Review</button>'+inboxReplyHTML();}}
    else if(o.type==='decision'){detail='<div class="space-y-1.5">'+(o.options||[]).map(op=>'<button data-comp="option-card" class="opt" onclick="pickDecision(this)"><span class="opt-nm">'+esc(op.nm)+'</span><span class="opt-desc">'+esc(op.desc)+'</span></button>').join('')+'</div>';
      acts='<button data-comp="button" class="btn-main btn-sm dec-approve" disabled title="Select an option first" onclick="inboxDecision(this)">Approve</button>'+inboxReplyHTML();}
    else if(o.type==='warning'){detail='<div class="rc-body">'+esc(o.body)+'</div>';
      /* Warning simplified per user: a Warning is a plain FYI — the cap-specific actions (Continue / Raise cap / Stop)
         and the generic Acknowledge are ALL gone, so a Warning carries no warning-specific dependency. Just two actions:
           · Dismiss — the completion action (clears the warning; a warning never auto-clears, only manual Dismiss).
             Styled PINK (btn-main) as this card's sole primary "commit here" (like the old Continue), NOT danger —
             danger stays on give-up/destructive actions (the Error card's Dismiss, Deny, Stop).
           · Reply — the shared teal hand-off every card carries (never completes the item).
         Warnings are notify-only and never hard-block: the run-state badge stays active and the run-strip keeps
         shimmering (only Permission/Plan/Decision/max-turns pause). */
      acts='<button data-comp="button" class="btn-main btn-sm" onclick="inboxResolve(this,\'Dismissed\')" title="Dismiss this warning (clears it from the Inbox)">Dismiss</button>'+inboxReplyHTML();}
    else if(o.type==='response'){detail='<div class="rc-body">'+esc(o.body)+'</div>';
      /* Next-up item 14: Response — the lone non-blocking card (a run ended with output the user hasn't
         reviewed). View (pink — this card's completion action, like the Warning's Dismiss) jumps to Feed →
         Messages scoped to the agent + flashes the run's final reply, and COMPLETES the item; the shared Reply
         ALSO completes here (inboxReply special-cases response). No Dismiss; no read-tracking. */
      acts='<button data-comp="button" class="btn-main btn-sm" onclick="inboxView(this)" title="View — jump to the run\'s final reply in Messages (completes this item)"><i data-lucide="eye" class="w-3 h-3"></i>View</button>'+inboxReplyHTML();}
    else{detail='<div class="rc-body inbox-err">'+esc(o.body)+'</div>';   /* Error: inline error text + Retry · Dismiss · Reply (no View, no Forward). Item 15: on a SYSTEM error card Reply is disabled — greyed, not removed. */
      acts='<button data-comp="button" class="btn-main btn-sm" onclick="inboxRetry(this)" title="Retry — load the last command into the Editor"><i data-lucide="rotate-ccw" class="w-3 h-3"></i>Retry</button><button data-comp="button" class="btn-danger btn-sm" onclick="inboxResolve(this,\'Dismissed\')">Dismiss</button>'+inboxReplyHTML(!!a.system);}
    const sub=o.subtype?'<span data-comp="inbox-subtype-badge" class="inbox-subtype'+(o.type==='warning'?' inbox-subtype--warning':'')+'">'+esc(o.subtype)+'</span>':'';   /* R11 item 1: emit the header subtype badge for any card carrying o.subtype (Error → red base, Warning → --warning variant); cards without a subtype render none */
    const runs=(o.type==='response'&&o.runs>1)?'<span data-comp="inbox-runs-chip" class="inbox-runs" title="'+o.runs+' unseen runs coalesced — a new unseen run updates this card, never stacks">×'+o.runs+' runs</span>':'';   /* item 14: the coalesce marker */
    const _inboxComp={error:'error-inbox-card',warning:'warning-inbox-card',permission:'permission-inbox-card',plan:'plan-inbox-card',decision:'decision-inbox-card',response:'response-inbox-card'}[o.type]||'error-inbox-card';   /* ND 16: the workflow card is its own component — emitted LITERALLY below so its approved/rejected round-trip states declare on its own slug */
    return (o.wf
      ?'<div data-comp="workflow-inbox-card" data-variants="reply-flash approved rejected" class="fcard inbox-card inbox-card--'+o.type+'" data-agent="'+o.ag+'" data-reqi="'+i+'">'
      :'<div data-comp="'+_inboxComp+'" data-variants="reply-flash" class="fcard inbox-card inbox-card--'+o.type+'" data-agent="'+o.ag+'" data-reqi="'+i+'">')
      +'<div class="fcard-head">'
      +'<button class="fcard-exp msel-head" onclick="fcardSel(event,this)" title="Select this request (Attach)">'+badgeHTML(a)+sub+runs
      +'<span class="inbox-title">'+esc(o.title)+'</span>'
      +'<span class="fcard-time">'+o.time+'</span></button>'
      +'<button class="fcard-chevbtn" onclick="toggleFcard(this)" title="Expand / collapse"><i data-lucide="chevron-right" class="fcard-chev"></i></button>'
      +'</div>'
      +'<div class="fcard-body"><div class="inbox-detail">'+detail+'</div><div class="inbox-acts">'+acts+'</div></div></div>';}
  /* OQ-2 resolved → folds: each typed section is an ACCORDION, expanded by default (all open for scanning).
     The band is a neutral --surface-3 fill with a LEADING chevron — deliberately distinct from the .fcard
     accordion (bordered right-side chevbtn + chevron-right). Clicking the band toggles the section. */
  function renderInbox(){const el=document.getElementById('inbox-list');if(el){
      let html='';INBOX_SECTIONS.forEach(sec=>{const items=REQS.filter(r=>r.type===sec.type);if(!items.length)return;
        html+='<div data-comp="inbox-section" class="inbox-sec inbox-sec--'+sec.type+' open">'
          +'<button class="inbox-sec-head" onclick="toggleInboxSec(this)" title="Collapse / expand this section"><i data-lucide="chevron-down" class="inbox-sec-chev"></i><span class="inbox-sec-lab">'+sec.lab+'</span><span data-comp="count-square" class="inbox-sec-n">'+items.length+'</span></button>'
          +'<div class="inbox-sec-cards">'+items.map(o=>inboxCardHTML(o,REQS.indexOf(o))).join('')+'</div></div>';});
      el.innerHTML=html;LU();}refreshInbox();}
  function toggleInboxSec(btn){const s=btn.closest('.inbox-sec');if(s)s.classList.toggle('open');LU();}
  function refreshInbox(){const n=document.querySelectorAll('#feed-inbox .fcard').length;
    const b=document.getElementById('inbox-badge');if(b){b.textContent=n;b.style.display=n?'':'none';}
    const aw=document.getElementById('inbox-await');if(aw)aw.textContent=n+' open item'+(n===1?'':'s')+' — blocking requests first, the non-blocking Response section last';}   /* item 14: "one open request each / N agents" no longer holds — Response is non-blocking and coalesces per agent */
  /* P2: after removing a card, drop its section if it's now empty, else update the section count */
  function inboxAfterRemove(sec){if(!sec)return;const cards=sec.querySelectorAll('.fcard');if(!cards.length){sec.remove();return;}const c=sec.querySelector('.inbox-sec-n');if(c)c.textContent=cards.length;}
  function inboxResolve(btn,verb){const card=btn.closest('.fcard');if(!card)return;const sec=card.closest('.inbox-sec');const nm=((card.querySelector('.b-name')||{}).textContent||'agent').trim();
    toast(verb+' — '+nm+' unblocked');card.style.transition='opacity .2s,transform .2s';card.style.opacity='0';card.style.transform='translateX(8px)';
    setTimeout(()=>{card.remove();inboxAfterRemove(sec);refreshInbox();},200);}
  /* Workflow Approve/Reject ROUND-TRIP: the card first shows its resolved state IN PLACE (the approved/rejected
     class — success/danger left edge + banner, actions gone, script dimmed) for a beat, then completes and
     leaves the Inbox like every resolved card. Approve = allow (launch) · Reject = deny (abort before launch). */
  function wfResolve(btn,ok){const card=btn.closest('.fcard');if(!card)return;const sec=card.closest('.inbox-sec');
    card.classList.add(ok?'approved':'rejected');
    const nm=((card.querySelector('.b-name')||{}).textContent||'agent').trim();
    toast(ok?('Approved — '+nm+'’s workflow launches'):('Rejected — '+nm+'’s workflow aborted before launch'));
    setTimeout(()=>{card.style.transition='opacity .2s,transform .2s';card.style.opacity='0';card.style.transform='translateX(8px)';
      setTimeout(()=>{card.remove();inboxAfterRemove(sec);refreshInbox();if(typeof renderNodeInboxes==='function')renderNodeInboxes();},200);},1600);}
  function inboxDecision(btn){const card=btn.closest('.fcard');const opt=card&&card.querySelector('.opt.on');if(!opt){toast('Select an option first');return;}
    const sec=card.closest('.inbox-sec');const nm=((card.querySelector('.b-name')||{}).textContent||'agent').trim();const lab=(opt.querySelector('.opt-nm')||{}).textContent||'option';
    toast('Approved '+lab+' — '+nm+' unblocked');card.style.transition='opacity .2s';card.style.opacity='0';
    setTimeout(()=>{card.remove();inboxAfterRemove(sec);refreshInbox();},200);}
  /* Next-up item 14: Response → View — hand off to Feed → Messages with the From/To filter scoped to
     that agent, then scroll + flash the run's FINAL REPLY (the agent's last parent-level message) — the
     plan-flash jump pattern (scroll + select-free flash, via the shared .reply-flash). Viewing COMPLETES the
     item (the deliberate seen/unseen model without read-tracking: reading Messages organically leaves it open). */
  function inboxView(btn){const card=btn.closest('.fcard');if(!card)return;const key=card.dataset.agent;
    if(typeof switchTab==='function')switchTab('feed','transcript');
    const fil=document.getElementById('feed-filter');
    if(fil){fil.querySelectorAll('.agrow.on').forEach(r=>r.classList.remove('on'));   /* scope the shared filter to just this agent (+ its subtree) */
      const row=[...fil.querySelectorAll('.agrow[data-ag]')].find(r=>r.dataset.ag===key);
      if(row){row.classList.add('on');
        if(row.classList.contains('agrow--parent')){const subs=row.nextElementSibling;if(subs&&subs.classList.contains('agrow-subs'))subs.querySelectorAll('.agrow--sub').forEach(s=>s.classList.add('on'));}}
      agSync(fil);updateAgBadges(fil);updateSubCounts(fil);}
    const cards=[...document.querySelectorAll('#tx-list .txcard')].filter(c=>{const m=MSGS[+c.dataset.msgi];return m&&m.ag===key&&!m.sub;});
    const last=cards[cards.length-1];
    if(last){last.scrollIntoView({block:'nearest',behavior:'smooth'});
      last.classList.remove('reply-flash');void last.offsetWidth;last.classList.add('reply-flash');setTimeout(()=>last.classList.remove('reply-flash'),1000);}
    const sec=card.closest('.inbox-sec');card.remove();inboxAfterRemove(sec);refreshInbox();   /* View completes the item */
    LU();toast('Response reviewed — jumped to the run\'s final reply');}
  /* P2: generalized Reply — pre-fill the Editor with a FROZEN embed reference block (P1a) of this card's
     contents, then pre-target the agent. Decision embeds the question + its options; the rest the detail.
     Item 14: on a RESPONSE card Reply also COMPLETES the item (it's the card's other completion path). */
  function inboxReply(btn){const card=btn.closest('.fcard');if(!card)return;const o=REQS[+card.dataset.reqi];const a=AG[card.dataset.agent];if(!o||!a)return;
    let body;if(o.type==='decision'){body=esc(o.title)+'\n\n'+(o.options||[]).map(op=>'• '+esc(op.nm)+' — '+esc(op.desc)).join('\n');}
    else{body=esc(o.title)+(o.body?('\n\n'+esc(o.body)):'')+(o.cmd?('\n\n$ '+esc(o.cmd)):'');}
    const block=blockHTML('embed',{source:'Inbox · '+secLabel(o.type)+' from '+a.role+' '+a.name,body:body,srcAction:"switchTab('feed','inbox')",clamp:true,kindLabel:'reply'});
    const f=document.getElementById('compose-field');if(f)f.insertAdjacentHTML('afterbegin',block);
    replyTo(a.name);
    if(o.type==='response'){const sec=card.closest('.inbox-sec');card.remove();inboxAfterRemove(sec);refreshInbox();}
    if(window.lucide&&lucide.createIcons)lucide.createIcons();toast('Reply drafted — '+a.name+' quoted in the Editor');}
  /* P2: Error Retry — load the last command into the Editor (routes through the Editor, not the Console) */
  function inboxRetry(btn){const card=btn.closest('.fcard');if(!card)return;const o=REQS[+card.dataset.reqi];const a=AG[card.dataset.agent];const cmd=(o&&(o.cmd||o.title))||'';
    const f=document.getElementById('compose-field');if(f)f.insertAdjacentHTML('afterbegin','<div>'+esc(cmd)+'</div>');
    if(a&&!a.user&&!a.system)replyTo(a.name);else switchTab('prompt','compose');   /* item 15: System isn't addressable — no pre-target */
    toast('Retry — last command loaded in the Editor');}

  /* shared send-to-agents control (Share on the feed · Review on a plan) */
  let _tt=null;
  function toast(msg){let t=document.getElementById('toast');if(!t){t=document.createElement('div');t.id='toast';t.className='toast';t.setAttribute('data-comp','toast');t.setAttribute('data-variants','show');document.body.appendChild(t);}t.textContent=msg;t.classList.add('show');clearTimeout(_tt);_tt=setTimeout(()=>t.classList.remove('show'),2400);}

  /* ===== v1.2: Console — raw feed + slash-command catalog (scoped to the focused agent) ===== */
  const CON_FEED=[
    {c:'l-status',t:'researcher · 01 sandy — claude-code v2.0.14 · model: opus 4.8 · cwd: ~/agent-dashboard'},
    {c:'l-cmd', t:'> audit the session + token-refresh path in src/auth for fixation risks'},
    {c:'l-think',t:'✻ Thinking… the cookie is reissued on refresh but the CSRF secret carries over — a privilege-boundary smell worth probing before I write this up.'},
    {c:'l-tool',t:'● Bash(grep -rn "refreshToken" src/auth)'},
    {c:'l-result',t:'⎿  6 matches across session.ts, tokens.ts'},
    {c:'l-tool',t:'● Read(src/auth/session.ts)'},
    {c:'l-result',t:'⎿  Read 212 lines'},
    {c:'l-asst',t:'I found a session-fixation risk in refreshToken(): the session cookie is reissued'},
    {c:'l-asst',t:'but the CSRF token is preserved across a privilege change, so a pre-auth token'},
    {c:'l-asst',t:'stays valid after login. Recommend rotating both together.'},
    {c:'l-tool',t:'● Update(src/auth/session.ts)'},
    {k:'diff',head:'Updated src/auth/session.ts with 3 additions and 1 removal',t:'  function refreshToken(req) {\n-   return reissue(req.session)\n+   const s = reissue(req.session)\n+   s.csrf = rotateCsrf()\n+   return s\n  }'},
    {c:'l-tool',t:'● Bash(rm -rf node_modules && pnpm install)'},
    {k:'perm',title:'Bash command',cmd:'rm -rf node_modules && pnpm install',q:'Do you want to proceed?',opts:['1. Yes',"2. Yes, and don't ask again for Bash commands in ~/agent-dashboard",'3. No, and tell Claude what to do differently (esc)']},
    {c:'l-cmd', t:'> /compact'},
    {c:'l-ok',  t:'⎿  Compacted context · 399.1k → 142.0k tokens'},
  ];
  const CON_CMDS=[
    {g:'Session & context', items:[
      ['/clear',"Wipe this agent's context and start fresh"],
      ['/compact','Summarize and shrink the context window'],
      ['/rewind','Roll this agent back to an earlier point'],
      ['/resume','Resume a previous session'],
      ['/export','Save this conversation to a file'],
    ]},
    {g:'Model & behavior', items:[
      ['/model',"Switch this agent's model",'Details'],
      ['/config','Open configuration','Settings'],
      ['/fast','Toggle Opus fast-mode','Details'],
      ['/think','Toggle extended thinking','Details'],
      ['/permissions','Review tool permissions'],
    ]},
    {g:'Info & status', items:[
      ['/cost','Token spend this session'],
      ['/context','Context-window breakdown'],
      ['/status','Health and connection'],
      ['/stats','Project statistics','Settings'],
    ]},
    {g:'Tools & integrations', items:[
      ['/mcp','MCP servers','Settings'],
      ['/agents','Subagents'],
      ['/hooks','Lifecycle hooks'],
      ['/plugin','Plugins and marketplaces','Settings'],
    ]},
    {g:'Project & custom', items:[
      ['/gsd:next','Advance to the next GSD step'],
      ['/gsd:progress','Check project progress'],
      ['/review','Request a code review'],
      ['/init','Generate a CLAUDE.md'],
    ]},
    {g:'System', items:[
      ['/help','List every command'],
      ['/doctor','Diagnose the install'],
      ['/login','Switch account'],
      ['/memory','Edit memory files'],
    ]},
  ];
  /* v10p1 #14: render a faithful Claude Code terminal line — colored native markers (● tool · ⎿ result ·
     ✻ thinking · > input), +/− diff blocks, and a permission-prompt box. */
  function conMarkup(t){const m=t.match(/^(\s*)(●|⎿|✻|>)(\s?)([\s\S]*)$/);
    if(m){const cls={'●':'cmk-bullet','⎿':'cmk-pipe','✻':'cmk-think','>':'cmk-prompt'}[m[2]];
      return esc(m[1])+'<span class="'+cls+'">'+m[2]+'</span>'+(m[3]||'')+esc(m[4]);}
    return esc(t);}
  function conDiffHTML(l){const head=l.head?'<div class="con-line l-result"><span class="cmk-pipe">⎿</span>  '+esc(l.head)+'</div>':'';
    const body=l.t.split('\n').map(ln=>{const c=ln[0]==='+'?'cdiff-add':(ln[0]==='-'?'cdiff-del':'cdiff-ctx');return '<div class="con-diff-ln '+c+'">'+esc(ln)+'</div>';}).join('');
    return head+'<div class="con-diff">'+body+'</div>';}
  function conPermHTML(l){return '<div class="con-perm"><div class="con-perm-h">'+esc(l.title)+'</div>'
    +(l.cmd?'<div class="con-perm-cmd">'+esc(l.cmd)+'</div>':'')
    +'<div class="con-perm-q">'+esc(l.q||'Do you want to proceed?')+'</div>'
    +'<div class="con-perm-opts">'+(l.opts||[]).map((o,i)=>'<div class="con-perm-opt'+(i===0?' sel':'')+'">'+(i===0?'❯ ':'  ')+esc(o)+'</div>').join('')+'</div></div>';}
  function conLineHTML(l){if(l.k==='perm')return conPermHTML(l);if(l.k==='diff')return conDiffHTML(l);
    return '<div class="con-line '+(l.c||'l-asst')+'">'+conMarkup(l.t)+'</div>';}
  function renderConsole(){
    const feed=CON_FEED.map(conLineHTML).join('');
    document.querySelectorAll('#con-feed-col,#con-feed-full').forEach(el=>{el.innerHTML=feed;el.scrollTop=el.scrollHeight;});
    const list=CON_CMDS.map(grp=>'<div class="cmd-group"><div class="cmd-group-h">'+esc(grp.g)+'</div>'+
      grp.items.map(it=>'<button class="cmd-row" onclick="pickCmd(this)" data-cmd="'+it[0]+'">'+
        '<span class="cmd-row-top"><span class="cmd-name">'+esc(it[0])+'</span>'+
        (it[2]?'<span class="cmd-also" title="Also available in '+it[2]+'"><i data-lucide="corner-up-right"></i>'+esc(it[2])+'</span>':'')+'</span>'+
        '<span class="cmd-desc">'+esc(it[1])+'</span></button>').join('')+
      '</div>').join('');
    document.querySelectorAll('[data-cmdlist]').forEach(el=>el.innerHTML=list);
    LU();
  }
  function conInput(ctx){ return (ctx&&ctx.closest&&ctx.closest('.console-view'))?document.getElementById('con-input-full'):document.getElementById('con-input-col'); }
  function pickCmd(el){
    const inp=conInput(el); if(inp){inp.value=el.dataset.cmd+' ';inp.focus();}
    if(!el.closest('.console-view')){const cat=document.getElementById('con-catalog-col');if(cat)cat.classList.remove('open');document.querySelectorAll('#mid-foot-console .con-cmds-btn').forEach(b=>b.classList.remove('on'));}
  }
  function toggleCmdPanel(btn){
    const cat=document.getElementById('con-catalog-col');if(!cat)return;
    const open=cat.classList.toggle('open');
    document.querySelectorAll('#mid-foot-console .con-cmds-btn').forEach(b=>b.classList.toggle('on',open));
    if(open){const s=cat.querySelector('.con-search input');if(s){s.value='';filterCmds(s);setTimeout(()=>s.focus({preventScroll:true}),0);}}
  }
  function filterCmds(inp){
    const scope=inp.closest('.con-catalog,.con-rail');if(!scope)return;const q=inp.value.trim().toLowerCase();
    scope.querySelectorAll('.cmd-row').forEach(r=>{r.style.display=(!q||r.textContent.toLowerCase().includes(q))?'':'none';});
    scope.querySelectorAll('.cmd-group').forEach(g=>{const any=[...g.querySelectorAll('.cmd-row')].some(r=>r.style.display!=='none');g.style.display=any?'':'none';});
  }
  function filterFocus(btn){const r=btn.closest('.console-view');const s=r?r.querySelector('.con-search input'):null;if(s)s.focus();}
  function runConsoleCmd(el){
    const inp=conInput(el);if(!inp)return;const v=inp.value.trim();if(!v){inp.focus();return;}
    CON_FEED.push({c:'l-cmd',t:'> '+v});
    CON_FEED.push({c:'l-sys',t:'⎿ '+(v[0]==='/'?'Ran '+v.split(/\s+/)[0]+' on researcher · 01 sandy':'Sent to researcher · 01 sandy')+' (mock)'});
    renderConsole();inp.value='';inp.focus();
    toast('Console: '+v+' → researcher · 01 sandy');
  }
  function openConsole(){
    const v=document.getElementById('console-view');if(!v)return;
    v.classList.add('open');v.setAttribute('aria-hidden','false');renderConsole();
    positionConsoleView();
    const s=v.querySelector('.con-search input');if(s){s.value='';filterCmds(s);}
    LU();
  }
  function closeConsole(){const v=document.getElementById('console-view');if(!v)return;v.classList.remove('open');v.setAttribute('aria-hidden','true');v.style.right='';}
  /* v10p1 #13: the Console step-into covers only the LEFT + MIDDLE columns — its right edge stops at the
     left edge of the right column (#pRight), so the Feed + Prompt stay visible. Recomputed on window
     resize and splitter drags (a ResizeObserver on #pRight fires for both). Settings keeps its full-window
     step-into — a deliberate difference (see DESIGN.md). */
  function positionConsoleView(){const v=document.getElementById('console-view');if(!v||!v.classList.contains('open'))return;
    const app=document.querySelector('.app'),pr=document.getElementById('pRight');if(!app||!pr)return;
    const a=app.getBoundingClientRect(),r=pr.getBoundingClientRect();
    v.style.right=Math.max(0,Math.round(a.right-r.left))+'px';}

  /* ===== hover-card primitive: data-hc (+ optional data-hc-title) on any element; info-glyph on panel headers ===== */
  function hcEl(){let p=document.getElementById('hcpop');if(!p){p=document.createElement('div');p.id='hcpop';p.setAttribute('data-comp','hover-card');p.innerHTML='<div class="hc-title"></div><div class="hc-body"></div>';document.body.appendChild(p);}return p;}
  function showHC(t){const txt=t.getAttribute('data-hc');if(!txt)return;const p=hcEl();const title=t.getAttribute('data-hc-title')||'';
    const tEl=p.querySelector('.hc-title');tEl.textContent=title;tEl.style.display=title?'':'none';p.querySelector('.hc-body').textContent=txt;
    const r=t.getBoundingClientRect();p.style.left=Math.max(8,Math.min(r.left,window.innerWidth-276))+'px';p.classList.add('open');
    let top=r.bottom+6;const ph=p.offsetHeight;if(top+ph>window.innerHeight-8)top=Math.max(8,r.top-ph-6);p.style.top=top+'px';}
  function hideHC(){const p=document.getElementById('hcpop');if(p)p.classList.remove('open');}
  document.addEventListener('mouseover',e=>{const t=e.target.closest&&e.target.closest('[data-hc]');if(t)showHC(t);});
  document.addEventListener('mouseout',e=>{const t=e.target.closest&&e.target.closest('[data-hc]');if(t&&!(e.relatedTarget&&t.contains&&t.contains(e.relatedTarget)))hideHC();});
  document.addEventListener('focusin',e=>{const t=e.target.closest&&e.target.closest('[data-hc]');if(t)showHC(t);});
  document.addEventListener('focusout',hideHC);
  /* pure-documentation content (no clickable links inside — routing stays on the real controls) */
  const HC={
    'Agent':"The selected agent — its identity, config, and live run state. Details (config + Context/Turns + Rewind/Handoff timeline) · Create (new-agent wizard) · Console (raw CLI feed + slash-command runner).",
    'Team':"The live roster, one card per agent. Click a card to focus that agent across the whole app. Each card shows identity, a health-colored Ctx + Turns bar, a status badge (active/idle/pending/error), a subagent strip, and model·mode·effort. Select agents and use Link Agents to connect them; directed link edges are planned.",
    'Library':"Organize and review the project's docs and assets. Plans (native plan files, reviewable with per-section feedback + Approve/Revise/Reject; the badge counts plans not yet reviewed) · Documents (README + project/user CLAUDE.md, line-numbered) · Assets (reference images — the single source of truth for media).",
    'Feed':"Real-time cross-agent view, narrowed by the shared agent From/To filter (persists across all four tabs). Transcript (team traffic; Sent/Received filter by direction, the content filters by block kind — Messages · Thinking · Files · Shell · Search · Workflow — and the Subagent toggle hides the entries nested inside each parent's card; select-to-act cards) · Scratch (live shared-scratchpad posts) · Log (system events) · Inbox (the requests you owe — Error · Warning · Permission · Review (plans, docs & workflow approvals) · Decision sections, plus the non-blocking Response section for run output you haven't reviewed; its badge is the fleet total).",
    'Prompt':"Compose and dispatch prompts — the compose-first heart of the app. On Compose, From (single) sets who it's sent as; on History, From becomes a multi-select filter (the To list minus Scratch — your own prompts always show). To (multi, led by the Scratch row) sets who receives it and persists across both tabs.",
    'Past':"Agents that are no longer live, in one drawer. Resumable merges every persisted agent that isn't on the roster — dead roster records + the archive, source-tagged — with a per-row Resume (relaunch on its own conversation, never a fork). Archive is the management lens over the same records: the full deep-freeze read (stamps, lineage, git author, transcript pointer) with Resume + Delete forever.",
    'Link Config':"Forwards context from one agent to another. The agent pair is two single-select dropdowns (the graph selection prepopulates them). Direction A→B / B→A / A↔B (default: both). Relationship (what flows — ONE per link; wanting both = two links): Direct messaging is a reply-to conversation · Shared context is passive awareness of selected content (Messages/Thinking/Files/Shell/Search/Workflow — the Transcript content taxonomy), optionally backfilled once. Trigger (when it delivers — a dropdown): Now interrupts · Inject feeds a running agent without stopping it · Next waits for the turn · Queue joins the prompt queue (the Direct-messaging default) · Hold stages for your approval · Piggyback never initiates — it rides the next message the target receives from any source (the Shared-context default; an actively-delivered share costs the target a turn to ingest). End After bounds this exchange in Exchanges/Tokens (on a one-way link each fire counts as an exchange) — distinct from an agent's own Lifecycle limits."
  };
  function seedHoverCards(){document.querySelectorAll('.pcard-head h3').forEach(h=>{const k=h.textContent.trim();const d=HC[k];if(!d)return;
    if(h.parentElement.querySelector('.hc-glyph'))return;
    const g=document.createElement('button');g.type='button';g.className='hc-glyph';g.tabIndex=0;g.setAttribute('data-comp','hover-card');g.setAttribute('data-hc',d);g.setAttribute('data-hc-title',k);g.setAttribute('aria-label',k+' — what this panel does');g.innerHTML='<i data-lucide="info"></i>';
    h.insertAdjacentElement('afterend',g);});LU();}

  /* ===== boot ===== */
  function boot(){
    if(!document.querySelector('.app'))return;   /* inert on non-mockup pages (historically the gallery, retired 2026-07-05); see file header */
    buildIconGrids();
    document.querySelectorAll('[data-rolecombo]').forEach(buildCombo);
    document.querySelectorAll('[data-msel]').forEach(buildMsel);
    document.querySelectorAll('[data-expmount]').forEach(m=>{m.outerHTML=expMenuHTML(m.dataset.expmount);});   /* R-batch items 6/9: mount the merged Export control into the Feed + History footers (static markup carries a placeholder span) */
    fillRosterLists();   /* Next-up item 6: mount every agent-selector list from the shared roster (before renderFeed, whose applyHistFilters reads the History-From selection) */
    renderAssets();renderDocs();renderPlans();renderFeed();renderConsole();fillAgLists();buildTemplateOptions();renderAttachStrip();renderLinkList();eaUpdateAll();
    renderPast();   /* Agent → Past: the resume picker + the archive roster */
    renderImportList();renderImportAgents();   /* Library Import drawer — pre-rendered so it opens instantly (and the states page clones a faithful specimen) */
    document.addEventListener('selectionchange',saveComposeRange);   /* v10p1 #22: remember the compose cursor so a template inserts where you left off */
    const sn=document.querySelector('.node.selected');if(sn)selectNode(sn);   /* sync the Agent panel + Console to the focused card on load (single-sources Turns/Ctx/identity) */
    const s=JSON.parse(localStorage.getItem('awl-v8')||'{}');Object.entries(s).forEach(([g,t])=>{if(g==='settings')return;switchTab(g,t);});   /* settings tab is not restored — it always opens on its default lead tab (Projects), even if a prior session saved another */
    const tas=document.querySelectorAll('textarea.autosize');tas.forEach(t=>t.addEventListener('input',()=>autosize(t)));autosizeAll();
    if(window.ResizeObserver){const ro=new ResizeObserver(es=>es.forEach(e=>autosize(e.target)));tas.forEach(t=>ro.observe(t));const gw=document.getElementById('graph-wrap');if(gw)new ResizeObserver(()=>drawEdges()).observe(gw);
      const pr=document.getElementById('pRight');if(pr)new ResizeObserver(positionConsoleView).observe(pr);}   /* v10p1 #13: keep the Console step-into's right edge pinned to #pRight on splitter/window resize */
    window.addEventListener('resize',positionConsoleView);
    document.querySelectorAll('[data-agscope]').forEach(s=>{agSync(s);updateAgBadges(s);});
    seedHoverCards();
    initResizers();updateFmt('fmt');initEditorMics();LU();drawEdgesSoon();
    initJumpPills();
    renderNodeInboxes();   /* per-card inbox footer — split the footer + mirror each agent's open Inbox items (before initSubsAcc so wrap accounts for the envelope) */
    initSubsAcc();   /* R-batch item 3: detect subagent-strip wrap (→ chevron/drawer) on load */
    {const gg=document.getElementById('graph-grid');if(gg&&window.ResizeObserver)new ResizeObserver(()=>initSubsAcc()).observe(gg);else window.addEventListener('resize',initSubsAcc);}   /* recompute wrap on any graph-grid resize (splitter drag OR window resize), falling back to the window event */
  }
  if(document.readyState!=='loading'){boot();projInit();}else window.addEventListener('DOMContentLoaded',()=>{boot();projInit();});
  window.addEventListener('load',()=>{autosizeAll();drawEdgesSoon();LU();});
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(()=>{autosizeAll();drawEdgesSoon();});
  document.addEventListener('click',e=>{if(!e.target.closest('.split')&&!e.target.closest('.fmt')&&!e.target.closest('.picker')&&!e.target.closest('.combo')&&!e.target.closest('.msel')&&!e.target.closest('.src-dd')&&!e.target.closest('.rev-chip')&&!e.target.closest('.vtally')&&!e.target.closest('.exp'))closeAllPopups();});   /* R-batch item 5: exempt .rev-chip — its menu carries the .src-pop class, so without this the chip's own opening click bubbled here and closeAllPopups() instantly re-closed the just-opened reviewer menu */
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){const sv=document.getElementById('settings-view');const cv=document.getElementById('console-view');const imp=document.getElementById('import-drawer');if(sv&&sv.classList.contains('open')){const pc=document.getElementById('proj-close-confirm');if(pc&&pc.classList.contains('show')){projCancelClose();}else{closeSettings();}}else if(cv&&cv.classList.contains('open')){closeConsole();}else if(imp&&!imp.classList.contains('hidden')){toggleImport(false);}else{closeAllPopups();if(typeof closeSrcAccordions==='function')closeSrcAccordions();}}});   /* Next-up item 8: Esc also closes the sticky accordion-selector drawers (outside clicks don't); the Library Import drawer closes on Esc too (before the generic popup sweep) */
  setInterval(()=>{const e=document.getElementById('clock');if(e)e.textContent=new Date().toLocaleTimeString();},1000);
  /* live-reload on save (design iteration) */
  (function(){let l=null;setInterval(async()=>{try{const r=await fetch(location.href,{method:'HEAD',cache:'no-store'});const m=r.headers.get('Last-Modified');if(l&&m&&m!==l)location.reload();l=m;}catch(e){}},500);})();
