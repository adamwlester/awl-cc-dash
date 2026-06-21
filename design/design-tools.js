/**
 * AWL Design Collaboration Overlay v0.2
 * Drop into any concept HTML: <script src="design-tools.js"></script>
 * Toggle: Ctrl+G or click the floating button
 */
(function() {
  let active = false;
  let mode = 'pin'; // 'pin' | 'measure'
  let pins = [];
  let rects = [];
  let dragStart = null;
  let dragRect = null;
  let pinCounter = 1;
  let rectCounter = 1;

  // --- Create overlay container ---
  const overlay = document.createElement('div');
  overlay.id = 'dt-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:99998;pointer-events:none;display:none;';

  // --- Grid canvas ---
  const gridCanvas = document.createElement('canvas');
  gridCanvas.id = 'dt-grid';
  gridCanvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;';
  overlay.appendChild(gridCanvas);

  // --- Mouse coordinate badge ---
  const coordBadge = document.createElement('div');
  coordBadge.id = 'dt-coords';
  coordBadge.style.cssText = `
    position:fixed; bottom:12px; left:12px; z-index:99999;
    background:#000; border:2px solid #fff; border-radius:6px;
    padding:6px 12px; font-family:'JetBrains Mono',monospace; font-size:14px;
    color:#fff; display:none; pointer-events:none; font-weight:600;
  `;
  coordBadge.textContent = '0, 0';

  // --- Annotations panel ---
  const annotPanel = document.createElement('div');
  annotPanel.id = 'dt-annot-panel';
  annotPanel.style.cssText = `
    position:fixed; top:50px; left:12px; z-index:99999;
    background:#000; border:2px solid #fff; border-radius:10px;
    padding:10px; display:none; flex-direction:column; gap:6px;
    font-family:'Inter',sans-serif; box-shadow:0 8px 30px rgba(0,0,0,0.7);
    width:260px; max-height:70vh; overflow-y:auto;
  `;
  const annotTitle = document.createElement('div');
  annotTitle.style.cssText = 'font-size:12px;font-weight:700;color:#fff;margin-bottom:2px;';
  annotTitle.textContent = 'Annotations';
  annotPanel.appendChild(annotTitle);
  const annotList = document.createElement('div');
  annotList.id = 'dt-annot-list';
  annotList.style.cssText = 'display:flex;flex-direction:column;gap:6px;';
  annotPanel.appendChild(annotList);

  // --- Toolbar ---
  const toolbar = document.createElement('div');
  toolbar.id = 'dt-toolbar';
  toolbar.style.cssText = `
    position:fixed; top:50px; right:12px; z-index:99999;
    background:#000; border:2px solid #fff; border-radius:10px;
    padding:8px; display:none; flex-direction:column; gap:4px;
    font-family:'Inter',sans-serif; box-shadow:0 8px 30px rgba(0,0,0,0.7);
  `;

  function tbBtn(label, emoji, onClick, id) {
    const btn = document.createElement('button');
    btn.id = id || '';
    btn.innerHTML = `${emoji} <span style="font-size:13px;font-weight:600">${label}</span>`;
    btn.style.cssText = `
      background:#222; border:2px solid #555; border-radius:6px;
      color:#fff; padding:8px 12px; cursor:pointer; font-size:14px;
      display:flex; align-items:center; gap:8px; white-space:nowrap;
      transition:all 0.1s;
    `;
    btn.onmouseenter = () => { if (!btn.classList.contains('dt-active')) btn.style.background = '#444'; };
    btn.onmouseleave = () => { if (!btn.classList.contains('dt-active')) btn.style.background = '#222'; };
    btn.onclick = onClick;
    return btn;
  }

  const pinBtn = tbBtn('Pin', '📌', () => setMode('pin'), 'dt-pin-btn');
  const measureBtn = tbBtn('Measure', '📏', () => setMode('measure'), 'dt-measure-btn');
  const gridBtn = tbBtn('Grid', '🔲', toggleGrid, 'dt-grid-btn');
  const clearBtn = tbBtn('Clear All', '🗑️', clearAll);
  const copyBtn = tbBtn('Copy Notes', '📋', copyAnnotations);

  toolbar.appendChild(pinBtn);
  toolbar.appendChild(measureBtn);
  toolbar.appendChild(gridBtn);
  toolbar.appendChild(clearBtn);
  toolbar.appendChild(copyBtn);

  // --- Toggle button ---
  const toggleBtn = document.createElement('button');
  toggleBtn.id = 'dt-toggle';
  toggleBtn.innerHTML = '📐';
  toggleBtn.title = 'Design Tools (Ctrl+G)';
  toggleBtn.style.cssText = `
    position:fixed; bottom:12px; right:12px; z-index:99999;
    width:40px; height:40px; border-radius:50%;
    background:#000; border:2px solid #fff; color:white;
    font-size:18px; cursor:pointer; display:flex; align-items:center;
    justify-content:center; box-shadow:0 4px 16px rgba(0,0,0,0.6);
    transition:all 0.15s;
  `;
  toggleBtn.onmouseenter = () => toggleBtn.style.background = '#333';
  toggleBtn.onmouseleave = () => toggleBtn.style.background = (active ? '#7c3aed' : '#000');
  toggleBtn.onclick = toggle;

  // --- Interaction layer ---
  const interactionLayer = document.createElement('div');
  interactionLayer.id = 'dt-interaction';
  interactionLayer.style.cssText = 'position:fixed;inset:0;z-index:99997;display:none;cursor:crosshair;';

  document.body.appendChild(overlay);
  document.body.appendChild(coordBadge);
  document.body.appendChild(annotPanel);
  document.body.appendChild(toolbar);
  document.body.appendChild(toggleBtn);
  document.body.appendChild(interactionLayer);

  // --- Grid drawing ---
  let gridVisible = false;

  function drawGrid() {
    const c = gridCanvas;
    c.width = window.innerWidth;
    c.height = window.innerHeight;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    if (!gridVisible) return;

    // 50px grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth = 0.5;
    for (let x = 0; x < c.width; x += 50) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, c.height); ctx.stroke();
    }
    for (let y = 0; y < c.height; y += 50) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(c.width, y); ctx.stroke();
    }

    // 100px major lines + labels
    ctx.strokeStyle = 'rgba(255,255,255,0.5)';
    ctx.lineWidth = 1;
    ctx.font = '14px JetBrains Mono, monospace';
    for (let x = 0; x < c.width; x += 100) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, c.height); ctx.stroke();
      if (x > 0) {
        ctx.fillStyle = '#000';
        ctx.fillRect(x + 1, 0, 32, 18);
        ctx.fillStyle = '#fff';
        ctx.fillText(x, x + 3, 14);
      }
    }
    for (let y = 0; y < c.height; y += 100) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(c.width, y); ctx.stroke();
      if (y > 0) {
        ctx.fillStyle = '#000';
        ctx.fillRect(0, y - 16, 32, 18);
        ctx.fillStyle = '#fff';
        ctx.fillText(y, 2, y - 2);
      }
    }
  }

  function toggleGrid() {
    gridVisible = !gridVisible;
    gridBtn.classList.toggle('dt-active', gridVisible);
    gridBtn.style.background = gridVisible ? '#7c3aed' : '#222';
    gridBtn.style.borderColor = gridVisible ? '#a78bfa' : '#555';
    drawGrid();
  }

  // --- Mode switching ---
  function setMode(m) {
    mode = m;
    pinBtn.style.background = m === 'pin' ? '#7c3aed' : '#222';
    pinBtn.style.borderColor = m === 'pin' ? '#a78bfa' : '#555';
    measureBtn.style.background = m === 'measure' ? '#7c3aed' : '#222';
    measureBtn.style.borderColor = m === 'measure' ? '#a78bfa' : '#555';
  }

  // --- Toggle overlay ---
  function toggle() {
    active = !active;
    overlay.style.display = active ? 'block' : 'none';
    coordBadge.style.display = active ? 'block' : 'none';
    toolbar.style.display = active ? 'flex' : 'none';
    annotPanel.style.display = active ? 'flex' : 'none';
    interactionLayer.style.display = active ? 'block' : 'none';
    toggleBtn.style.background = active ? '#7c3aed' : '#000';
    toggleBtn.style.borderColor = active ? '#a78bfa' : '#fff';
    if (active) {
      setMode('pin');
      drawGrid();
    }
  }

  // --- Mouse tracking ---
  document.addEventListener('mousemove', (e) => {
    if (!active) return;
    coordBadge.textContent = `${e.clientX}, ${e.clientY}`;
    if (dragStart && mode === 'measure') {
      updateDragPreview(e.clientX, e.clientY);
    }
  });

  // --- Click/drag handling ---
  interactionLayer.addEventListener('mousedown', (e) => {
    if (mode === 'pin') {
      addPin(e.clientX, e.clientY);
    } else if (mode === 'measure') {
      dragStart = { x: e.clientX, y: e.clientY };
      dragRect = document.createElement('div');
      dragRect.className = 'dt-drag-preview';
      dragRect.style.cssText = `
        position:fixed; border:2px dashed #a78bfa; background:rgba(167,139,250,0.1);
        pointer-events:none; z-index:99998;
      `;
      document.body.appendChild(dragRect);
    }
  });

  interactionLayer.addEventListener('mouseup', (e) => {
    if (dragStart && mode === 'measure') {
      const r = normalizeRect(dragStart.x, dragStart.y, e.clientX, e.clientY);
      // Always clean up the preview
      if (dragRect) { dragRect.remove(); dragRect = null; }
      if (r.w > 5 && r.h > 5) {
        addRect(r);
      }
      dragStart = null;
    }
  });

  // Also handle mouse leaving the window during drag
  document.addEventListener('mouseleave', () => {
    if (dragStart && dragRect) {
      dragRect.remove();
      dragRect = null;
      dragStart = null;
    }
  });

  function updateDragPreview(mx, my) {
    if (!dragRect) return;
    const r = normalizeRect(dragStart.x, dragStart.y, mx, my);
    dragRect.style.left = r.x + 'px';
    dragRect.style.top = r.y + 'px';
    dragRect.style.width = r.w + 'px';
    dragRect.style.height = r.h + 'px';
  }

  function normalizeRect(x1, y1, x2, y2) {
    return {
      x: Math.min(x1, x2), y: Math.min(y1, y2),
      w: Math.abs(x2 - x1), h: Math.abs(y2 - y1)
    };
  }

  // --- Refresh annotations panel ---
  function refreshAnnotPanel() {
    annotList.innerHTML = '';

    if (pins.length === 0 && rects.length === 0) {
      const empty = document.createElement('div');
      empty.style.cssText = 'font-size:11px;color:#888;padding:4px;';
      empty.textContent = 'Drop pins or draw boxes to add annotations';
      annotList.appendChild(empty);
      return;
    }

    pins.forEach(p => {
      const row = document.createElement('div');
      row.style.cssText = 'background:#111;border:1px solid #444;border-radius:6px;padding:6px 8px;';
      row.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:between;gap:6px;margin-bottom:4px;">
          <span style="background:#ef4444;color:#fff;font-weight:700;font-size:11px;width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;">${p.id}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#fff;font-weight:600;">Pin (${p.x}, ${p.y})</span>
        </div>
        <input type="text" placeholder="Add note..." data-type="pin" data-id="${p.id}" value="${p.note || ''}"
          style="width:100%;background:#000;border:1px solid #555;border-radius:4px;padding:4px 6px;font-size:11px;color:#fff;font-family:'Inter',sans-serif;outline:none;box-sizing:border-box;">
      `;
      row.querySelector('input').addEventListener('input', (e) => {
        p.note = e.target.value;
      });
      annotList.appendChild(row);
    });

    rects.forEach(r => {
      const row = document.createElement('div');
      row.style.cssText = 'background:#111;border:1px solid #444;border-radius:6px;padding:6px 8px;';
      row.innerHTML = `
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
          <span style="background:#7c3aed;color:#fff;font-weight:700;font-size:11px;width:20px;height:20px;border-radius:4px;display:flex;align-items:center;justify-content:center;">${r.id}</span>
          <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#fff;font-weight:600;">${r.w}×${r.h} at (${r.x}, ${r.y})</span>
        </div>
        <input type="text" placeholder="Add note..." data-type="rect" data-id="${r.id}" value="${r.note || ''}"
          style="width:100%;background:#000;border:1px solid #555;border-radius:4px;padding:4px 6px;font-size:11px;color:#fff;font-family:'Inter',sans-serif;outline:none;box-sizing:border-box;">
      `;
      row.querySelector('input').addEventListener('input', (e) => {
        r.note = e.target.value;
      });
      annotList.appendChild(row);
    });
  }

  // --- Add pin ---
  function addPin(x, y) {
    const id = pinCounter++;
    const pinData = { id, x, y, note: '' };
    pins.push(pinData);

    const pin = document.createElement('div');
    pin.className = 'dt-pin';
    pin.dataset.id = id;
    pin.style.cssText = `
      position:fixed; left:${x - 14}px; top:${y - 14}px; z-index:99998;
      width:28px; height:28px; border-radius:50%;
      background:#ef4444; border:3px solid #fff;
      display:flex; align-items:center; justify-content:center;
      font-size:13px; font-weight:800; color:#fff;
      font-family:'Inter',sans-serif;
      box-shadow:0 2px 12px rgba(0,0,0,0.6);
      pointer-events:auto; cursor:pointer;
    `;
    pin.textContent = id;
    pin.title = `Pin ${id}: (${x}, ${y}) — click to remove`;

    const label = document.createElement('div');
    label.className = 'dt-pin-label';
    label.style.cssText = `
      position:fixed; left:${x + 18}px; top:${y - 10}px; z-index:99998;
      background:#000; border:2px solid #fff; border-radius:4px;
      padding:2px 8px; font-family:'JetBrains Mono',monospace;
      font-size:13px; color:#fff; pointer-events:none; white-space:nowrap;
      font-weight:600;
    `;
    label.textContent = `${x}, ${y}`;

    pin.onclick = () => {
      pins = pins.filter(p => p.id !== id);
      pin.remove();
      label.remove();
      refreshAnnotPanel();
    };

    document.body.appendChild(pin);
    document.body.appendChild(label);
    refreshAnnotPanel();
  }

  // --- Add measurement rect ---
  function addRect(r) {
    const id = rectCounter++;
    const rectData = { ...r, id, note: '' };
    rects.push(rectData);

    const rectEl = document.createElement('div');
    rectEl.className = 'dt-rect';
    rectEl.dataset.id = id;
    rectEl.style.cssText = `
      position:fixed; left:${r.x}px; top:${r.y}px;
      width:${r.w}px; height:${r.h}px; z-index:99998;
      border:3px solid #a78bfa; background:rgba(167,139,250,0.08);
      pointer-events:auto; cursor:pointer;
    `;
    rectEl.title = `Box ${id}: ${r.w}×${r.h} at (${r.x}, ${r.y}) — click to remove`;

    // ID badge in top-left corner
    const idBadge = document.createElement('div');
    idBadge.style.cssText = `
      position:absolute; top:-14px; left:-14px;
      background:#7c3aed; color:#fff; font-weight:800;
      font-size:13px; width:28px; height:28px; border-radius:4px;
      display:flex; align-items:center; justify-content:center;
      font-family:'Inter',sans-serif; border:2px solid #fff;
    `;
    idBadge.textContent = id;
    rectEl.appendChild(idBadge);

    // Dimension label
    const dimLabel = document.createElement('div');
    dimLabel.style.cssText = `
      position:absolute; top:-14px; left:24px;
      background:#000; border:2px solid #fff; border-radius:4px;
      padding:2px 8px; font-family:'JetBrains Mono',monospace;
      font-size:13px; color:#fff; white-space:nowrap; font-weight:600;
    `;
    dimLabel.textContent = `${r.w} × ${r.h}`;
    rectEl.appendChild(dimLabel);

    // Position label
    const posLabel = document.createElement('div');
    posLabel.style.cssText = `
      position:absolute; bottom:-20px; left:0;
      background:#000; border:2px solid #888; border-radius:4px;
      padding:1px 6px; font-family:'JetBrains Mono',monospace;
      font-size:11px; color:#fff; white-space:nowrap; font-weight:500;
    `;
    posLabel.textContent = `(${r.x}, ${r.y})`;
    rectEl.appendChild(posLabel);

    rectEl.onclick = (e) => {
      // Prevent click from bubbling if user clicks the rect
      rects = rects.filter(rc => rc.id !== id);
      rectEl.remove();
      refreshAnnotPanel();
    };

    document.body.appendChild(rectEl);
    refreshAnnotPanel();
  }

  // --- Clear all ---
  function clearAll() {
    pins = []; rects = []; pinCounter = 1; rectCounter = 1;
    document.querySelectorAll('.dt-pin, .dt-pin-label, .dt-rect, .dt-drag-preview').forEach(el => el.remove());
    refreshAnnotPanel();
  }

  // --- Copy annotations ---
  function copyAnnotations() {
    let text = `=== Design Annotations ===\nViewport: ${window.innerWidth}×${window.innerHeight}\n\n`;

    if (pins.length) {
      text += 'PINS:\n';
      pins.forEach(p => {
        text += `  #${p.id}: (${p.x}, ${p.y})`;
        if (p.note) text += ` — ${p.note}`;
        text += '\n';
      });
      text += '\n';
    }

    if (rects.length) {
      text += 'MEASUREMENTS:\n';
      rects.forEach(r => {
        text += `  #${r.id}: ${r.w}×${r.h} at (${r.x}, ${r.y})`;
        if (r.note) text += ` — ${r.note}`;
        text += '\n';
      });
      text += '\n';
    }

    if (!pins.length && !rects.length) {
      text += 'No annotations yet.\n';
    }

    navigator.clipboard.writeText(text).then(() => {
      copyBtn.querySelector('span').textContent = 'Copied!';
      copyBtn.style.background = '#16a34a';
      copyBtn.style.borderColor = '#22c55e';
      setTimeout(() => {
        copyBtn.querySelector('span').textContent = 'Copy Notes';
        copyBtn.style.background = '#222';
        copyBtn.style.borderColor = '#555';
      }, 1500);
    });
  }

  // --- Keyboard shortcuts ---
  document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'g') { e.preventDefault(); toggle(); }
    if (active && e.key === 'Escape') toggle();
  });

  window.addEventListener('resize', () => { if (active && gridVisible) drawGrid(); });

})();
