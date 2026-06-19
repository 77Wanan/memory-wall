// === 配置 ===
const API_BASE = 'http://localhost:8000';
const PAGE_SIZE = 50;

let notes = [];
let currentPage = 1;
let totalNotes = 0;
let loading = false;
let hasMore = true;

let filter = 'all';
let search = '';
let editId = null;
let searchMode = 'keyword';
let semanticResults = null;

let inputMode = 'short';
let isNight = false;

// === 昼夜 ===
document.getElementById('themeBtn').onclick = function() {
  isNight = !isNight;
  document.documentElement.setAttribute('data-theme', isNight ? 'night' : 'day');
  this.textContent = isNight ? '🌙 夜' : '☀️ 昼';
};

document.getElementById('modeShort').onclick = function() {
  inputMode = 'short';
  this.classList.add('active');
  document.getElementById('modeLong').classList.remove('active');
  document.getElementById('newNote').classList.remove('long-mode');
};
document.getElementById('modeLong').onclick = function() {
  inputMode = 'long';
  this.classList.add('active');
  document.getElementById('modeShort').classList.remove('active');
  document.getElementById('newNote').classList.add('long-mode');
};

// === 草稿箱（localStorage）===
const DRAFT_KEY = 'memory_wall_draft';

function saveDraft() {
  const title = document.getElementById('noteTitle').value.trim();
  const content = document.getElementById('newNote').value.trim();
  const tag = document.getElementById('newTag').value;
  if (!title && !content) {
    localStorage.removeItem(DRAFT_KEY);
    return;
  }
  localStorage.setItem(DRAFT_KEY, JSON.stringify({ title, content, tag, time: Date.now() }));
}

function restoreDraft() {
  const raw = localStorage.getItem(DRAFT_KEY);
  if (!raw) return;
  try {
    const draft = JSON.parse(raw);
    if (!draft.content && !draft.title) return;
    // Show a subtle restore option
    const banner = document.createElement('div');
    banner.style.cssText = 'max-width:100%;margin:0 auto 12px;padding:8px 14px;background:var(--card-bg);border:1px solid var(--border);border-radius:12px;font-size:13px;color:var(--text-mid);display:flex;align-items:center;gap:12px;';
    banner.innerHTML = '<span>✎ 你有一段未保存的草稿（' + new Date(draft.time).toLocaleTimeString() + '）</span>' +
      '<button id="restoreDraftBtn" style="margin-left:auto;padding:4px 12px;border:1px solid var(--border);border-radius:8px;background:var(--tag-bg);color:var(--text);font-size:12px;cursor:pointer;font-family:inherit;">恢复</button>' +
      '<button id="discardDraftBtn" style="padding:4px 8px;border:none;background:none;color:var(--text-dim);font-size:12px;cursor:pointer;font-family:inherit;">✕</button>';
    document.getElementById('inputRow').before(banner);
    document.getElementById('restoreDraftBtn').onclick = () => {
      document.getElementById('noteTitle').value = draft.title || '';
      document.getElementById('newNote').value = draft.content || '';
      document.getElementById('newTag').value = draft.tag || '默认';
      banner.remove();
    };
    document.getElementById('discardDraftBtn').onclick = () => {
      localStorage.removeItem(DRAFT_KEY);
      banner.remove();
    };
  } catch (e) { /* ignore corrupt draft */ }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY);
}

// 输入时自动存草稿
document.getElementById('noteTitle').oninput = saveDraft;
document.getElementById('newNote').oninput = saveDraft;
document.getElementById('newTag').onchange = saveDraft;

// === 笔记加载（分页）===
async function loadNotes(reset = true) {
  if (loading) return;
  if (reset) {
    currentPage = 1;
    notes = [];
    hasMore = true;
  }
  if (!hasMore) return;

  loading = true;
  const loadMoreBtn = document.getElementById('loadMoreBtn');
  if (loadMoreBtn) loadMoreBtn.textContent = '加载中…';

  try {
    const res = await fetch(`${API_BASE}/notes?page=${currentPage}&limit=${PAGE_SIZE}`);
    const data = await res.json();
    if (reset) {
      notes = data.notes;
    } else {
      notes = notes.concat(data.notes);
    }
    totalNotes = data.total;
    hasMore = currentPage * PAGE_SIZE < totalNotes;
    currentPage++;
  } catch (e) {
    if (reset) notes = [];
  }
  loading = false;
  render();
  flt();
  renderLoadMore();
}

function renderLoadMore() {
  const container = document.getElementById('loadMoreContainer');
  if (!hasMore || search.trim() || semanticResults) {
    container.innerHTML = '';
    return;
  }
  container.innerHTML = '<button id="loadMoreBtn" style="display:block;margin:20px auto;padding:8px 24px;border:1px solid var(--border);border-radius:12px;background:var(--card-bg);color:var(--text-mid);font-size:13px;cursor:pointer;font-family:inherit;transition:all .2s;">加载更多（' + notes.length + '/' + totalNotes + '）</button>';
  const btn = document.getElementById('loadMoreBtn');
  if (btn) btn.onclick = () => loadNotes(false);
}

// === 搜索 ===
document.getElementById('searchModeBtn').onclick = function() {
  searchMode = searchMode === 'keyword' ? 'semantic' : 'keyword';
  this.textContent = searchMode === 'keyword' ? '关键词' : '语义';
  this.classList.toggle('active');
  if (searchMode === 'keyword') {
    semanticResults = null;
  } else if (search.trim()) {
    doSemanticSearch(search);
  }
  render();
};

async function doSemanticSearch(q) {
  try {
    const res = await fetch(API_BASE+'/search/vector?q='+encodeURIComponent(q));
    const data = await res.json();
    semanticResults = data.results || [];
  } catch(e) {
    semanticResults = [];
  }
  render();
}

const icons = {'默认':'📌','学习':'📖','日常':'☕','技术':'⚙️','灵感':'💡','心情':'❤️'};
const order = ['默认','学习','日常','技术','灵感','心情'];

// === 渲染 ===
function getFilteredNotes() {
  if (searchMode === 'semantic' && semanticResults) {
    return semanticResults;
  }
  let list = notes;
  if (filter !== 'all') list = list.filter(n => n.tag === filter);
  if (search.trim()) {
    const q = search.trim().toLowerCase();
    list = list.filter(n => n.content.toLowerCase().includes(q) || (n.title||'').toLowerCase().includes(q));
  }
  return list;
}

function renderSidebar() {
  const sList = document.getElementById('sidebarList');
  let items = [...getFilteredNotes()].reverse();
  if (!items.length) { sList.innerHTML = '<div style="font-size:12px;color:var(--text-dim);padding:8px;">暂无记忆</div>'; return; }
  sList.innerHTML = items.map(n => {
    const t = n.title || (n.content.slice(0,20)+(n.content.length>20?'…':''));
    const p = n.title ? n.content.slice(0,30)+(n.content.length>30?'…':'') : '';
    const c = n.title ? '' : 'no-title';
    return '<div class="sidebar-item" data-id="'+n.id+'"><div class="s-title '+c+'">'+t+'</div>'+(p?'<div class="s-preview">'+p+'</div>':'')+'<span class="s-tag">'+(n.tag||'默认')+'</span></div>';
  }).join('');
  document.querySelectorAll('.sidebar-item').forEach(el => {
    el.onclick = function() {
      const id = parseInt(this.dataset.id);
      const n = notes.find(x => x.id === id);
      if (!n) return;
      showNoteDetail(n);
      sidebar.classList.remove('open');
      backdrop.classList.remove('show');
    };
  });
}

function showNoteDetail(n) {
  document.getElementById('floatTag').textContent = (icons[n.tag||'默认']||'')+' '+(n.tag||'默认');
  document.getElementById('floatTitle').textContent = n.title||'';
  document.getElementById('floatTitle').style.display = n.title ? 'block' : 'none';
  document.getElementById('floatContent').textContent = n.content;
  const d = new Date(n.time);
  document.getElementById('floatTime').textContent = (d.getMonth()+1)+'/'+d.getDate()+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
  document.getElementById('floatView').classList.add('show');
}

function render() {
  const c = document.getElementById('groupContainer');
  document.getElementById('stats').textContent = totalNotes + ' 条';
  let list = getFilteredNotes();
  const groups = {};
  list.forEach(n => { const t = n.tag||'默认'; if(!groups[t]) groups[t]=[]; groups[t].push(n); });
  const keys = order.filter(k => groups[k]);
  if (!keys.length) { c.innerHTML = '<div class="wall"><div class="empty"><span class="icon">✧</span>还没有记忆<br>写一条吧</div></div>'; renderSidebar(); return; }
  let html = '';
  keys.forEach(tag => {
    const items = groups[tag];
    html += '<div class="section-title"><span>'+icons[tag]+' '+tag+'</span><span class="count">'+items.length+'</span><span class="line"></span></div><div class="wall">';
    items.forEach(n => {
      const d = new Date(n.time);
      const t = (d.getMonth()+1)+'/'+d.getDate()+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0');
      const et = n.tag||'默认';
      const hc = n.title ? 'card has-title' : 'card';
      html += '<div class="'+hc+'" data-id="'+n.id+'"><span class="card-tag" data-tag="'+et+'">'+icons[et]+' '+et+'</span>';
      if (n.title) html += '<div class="card-title">'+n.title+'</div>';
      html += '<div class="card-content">'+n.content.replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</div><div class="card-time">'+t+'</div><div class="card-actions"><button class="edit-btn" data-id="'+n.id+'">✎</button><button class="delete-btn" data-id="'+n.id+'">✕</button></div></div>';
    });
    html += '</div>';
  });
  c.innerHTML = html;
  document.querySelectorAll('.card').forEach(el => {
    el.onclick = function(e) {
      if (e.target.closest('.card-actions')) return;
      const id = parseInt(this.dataset.id);
      const n = notes.find(x => x.id === id);
      if (!n) return;
      showNoteDetail(n);
    };
  });
  document.querySelectorAll('.edit-btn').forEach(b => b.onclick = (e) => { e.stopPropagation(); openEdit(+b.dataset.id); });
  document.querySelectorAll('.delete-btn').forEach(b => b.onclick = async (e) => {
    e.stopPropagation();
    const id = +b.dataset.id;
    if (!confirm('确定删除这条笔记吗？')) return;
    try {
      const res = await fetch(API_BASE+'/notes/'+id, {method:'DELETE'});
      if (!res.ok) throw new Error('删除失败');
      notes = notes.filter(x => x.id !== id);
      totalNotes = Math.max(0, totalNotes - 1);
      render();
      flt();
      renderLoadMore();
    } catch(e) {
      alert('删除失败');
    }
  });
  renderSidebar();
}

document.getElementById('floatClose').onclick = () => { document.getElementById('floatView').classList.remove('show'); };
document.getElementById('floatView').onclick = (e) => { if (e.target === document.getElementById('floatView')) document.getElementById('floatView').classList.remove('show'); };

// === 新建笔记 ===
async function add() {
  const ta = document.getElementById('newNote');
  const title = document.getElementById('noteTitle').value.trim();
  const c = ta.value.trim();
  if (!c) return;
  try {
    const res = await fetch(API_BASE+'/notes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title, content:c, tag:document.getElementById('newTag').value})});
    if (!res.ok) throw new Error('保存失败');
    const data = await res.json();
    notes.unshift({id:data.id, title, content:c, tag:document.getElementById('newTag').value, time:Date.now()});
    totalNotes++;
    ta.value = '';
    document.getElementById('noteTitle').value = '';
    clearDraft();
    render();
    flt();
    renderLoadMore();
  } catch(e) {
    // 失败时保留内容到 textarea，不清空
    alert('保存失败，内容已保留在输入框中');
  }
}

function openEdit(id) {
  const n = notes.find(x => x.id === id);
  if (!n) return;
  editId = id;
  document.getElementById('editTitle').value = n.title || '';
  document.getElementById('editContent').value = n.content;
  document.getElementById('editTag').value = n.tag;
  document.getElementById('modal').classList.add('show');
}

document.getElementById('cancelEdit').onclick = () => { document.getElementById('modal').classList.remove('show'); editId = null; };
document.getElementById('saveEdit').onclick = async () => {
  if (!editId) return;
  const c = document.getElementById('editContent').value.trim();
  if (!c) return;
  const title = document.getElementById('editTitle').value.trim()||'';
  const tag = document.getElementById('editTag').value;
  try {
    const res = await fetch(API_BASE+'/notes/'+editId, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title, content:c, tag})});
    if (!res.ok) throw new Error('保存失败');
    const n = notes.find(x => x.id === editId);
    if (n) { n.title = title; n.content = c; n.tag = tag; n.time = Date.now(); }
    document.getElementById('modal').classList.remove('show');
    editId = null;
    render();
    flt();
  } catch(e) {
    alert('保存失败，内容已保留在编辑框中');
  }
};

function flt() {
  const tags = new Set(notes.map(n => n.tag));
  let h = '<span class="filter-tag '+(filter==='all'?'active':'')+'" data-tag="all">全部</span>';
  order.forEach(t => { if (tags.has(t)) h += '<span class="filter-tag '+(filter===t?'active':'')+'" data-tag="'+t+'">'+icons[t]+' '+t+'</span>'; });
  document.getElementById('filters').innerHTML = h;
  document.querySelectorAll('.filter-tag').forEach(el => {
    el.onclick = () => { filter = el.dataset.tag; document.querySelectorAll('.filter-tag').forEach(e => e.classList.remove('active')); el.classList.add('active'); render(); };
  });
}

document.getElementById('searchInput').oninput = (e) => {
  search = e.target.value;
  if (searchMode === 'semantic' && search.trim()) {
    doSemanticSearch(search);
  } else {
    if (searchMode === 'semantic') semanticResults = null;
    render();
  }
};
document.getElementById('newNote').onkeydown = (e) => {
  if (e.isComposing || e.key !== 'Enter') return;
  if (e.shiftKey) return; // Shift+Enter → newline always
  // Mobile: never intercept Enter, always insert newline
  if ('ontouchstart' in window) return;
  if (inputMode === 'long' && !e.ctrlKey && !e.metaKey) return; // Enter → newline in long mode
  e.preventDefault();
  add();
};
document.getElementById('addBtn').onclick = add;

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('sw.js');
}

// Hamburger sidebar toggle
const sidebar = document.getElementById('sidebar');
const backdrop = document.getElementById('sidebarBackdrop');
document.getElementById('hamburgerBtn').onclick = () => {
  sidebar.classList.toggle('open');
  backdrop.classList.toggle('show');
};
backdrop.onclick = () => {
  sidebar.classList.remove('open');
  backdrop.classList.remove('show');
};

// Export / Import
document.getElementById('exportBtn').onclick = () => {
  const data = JSON.stringify(notes, null, 2);
  const blob = new Blob([data], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '记忆墙备份_'+new Date().toISOString().slice(0,10)+'.json';
  a.click();
  URL.revokeObjectURL(a.href);
};
document.getElementById('importBtn').onclick = () => {
  document.getElementById('importFile').click();
};
document.getElementById('importFile').onchange = (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    try {
      const imported = JSON.parse(ev.target.result);
      if (!Array.isArray(imported)) throw '格式错误';
      const existingIds = new Set(notes.map(n => n.id));
      imported.forEach(n => { if (!existingIds.has(n.id)) { notes.push(n); } });
      totalNotes = notes.length;
      render(); flt();
      alert('导入成功，新增 '+(imported.filter(n => !existingIds.has(n.id)).length)+' 条记忆');
    } catch(e) { alert('导入失败：文件格式不正确'); }
  };
  reader.readAsText(file);
  e.target.value = '';
};

// 页面加载
restoreDraft();
loadNotes(true);

// === Chat AI ===
let chatHistory = [];
let isStreaming = false;

const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('chatSend');

document.getElementById('chatBtn').onclick = () => {
  document.getElementById('chatPanel').classList.toggle('show');
};
document.getElementById('chatClose').onclick = () => {
  document.getElementById('chatPanel').classList.remove('show');
};
document.getElementById('chatClear').onclick = () => {
  chatHistory = [];
  chatMessages.innerHTML = '<div class="chat-msg ai">你好！我是你的笔记助手，可以帮你搜索和整理笔记内容。</div>';
};

function addChatMsg(role, text) {
  const el = document.createElement('div');
  el.className = 'chat-msg ' + role;
  el.textContent = text;
  chatMessages.appendChild(el);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return el;
}

function chatSetStatus(text) {
  let el = chatMessages.querySelector('.chat-msg.status:last-child');
  if (!el || el.dataset.active !== '1') {
    el = document.createElement('div');
    el.className = 'chat-msg status';
    el.dataset.active = '1';
    chatMessages.appendChild(el);
  }
  el.textContent = text;
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function chatClearStatus() {
  const el = chatMessages.querySelector('.chat-msg.status[data-active="1"]');
  if (el) el.remove();
}

async function doChat() {
  const msg = chatInput.value.trim();
  if (!msg || isStreaming) return;
  chatInput.value = '';

  addChatMsg('user', msg);
  chatHistory.push({ role: 'user', content: msg });

  const aiEl = addChatMsg('ai', '');
  isStreaming = true;
  chatSend.disabled = true;

  try {
    const res = await fetch(API_BASE + '/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, history: chatHistory.slice(0, -1) }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let fullContent = '';
    let evt = '', dat = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      const lines = buf.split('\n');
      buf = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('event: ')) evt = line.slice(7);
        else if (line.startsWith('data: ')) dat = line.slice(6);
        else if (line === '' && evt) {
          if (evt === 'token') {
            fullContent += dat;
            aiEl.textContent = fullContent;
            chatMessages.scrollTop = chatMessages.scrollHeight;
          } else if (evt === 'status') {
            chatSetStatus(dat);
          } else if (evt === 'error') {
            aiEl.textContent = '错误：' + dat;
          }
          evt = ''; dat = '';
        }
      }
    }
    chatClearStatus();
    if (fullContent) {
      chatHistory.push({ role: 'assistant', content: fullContent });
    }
  } catch (e) {
    aiEl.textContent = '连接失败，请确认后端正在运行。';
  }

  isStreaming = false;
  chatSend.disabled = false;
}

chatSend.onclick = doChat;
chatInput.onkeydown = (e) => {
  if (e.key === 'Enter' && !e.isComposing) {
    e.preventDefault();
    doChat();
  }
};
