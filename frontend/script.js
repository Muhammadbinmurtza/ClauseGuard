/* ═══════════════════════════════════════════════════════════════════════════
   ClauseGuard — Frontend JavaScript
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── API Configuration ── */
  const API_BASE = window.location.origin;
  let useServer = false;
  let chatContext = '';

  async function checkServer() {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) { useServer = true; return true; }
    } catch (_) { /* offline — use mock */ }
    useServer = false;
    return false;
  }

  /* ── Severity Color Map ── */
  const SEV = {
    CRITICAL: { badge: '🔴 CRITICAL', color: '#ff4444', light: '#ff6b6b', bg: 'rgba(255,68,68,0.10)', tagBg: 'rgba(255,68,68,0.15)', border: '#ff4444', cssClass: 'critical' },
    HIGH:     { badge: '🟠 HIGH',     color: '#ff8c00', light: '#ffaa44', bg: 'rgba(255,140,0,0.10)',  tagBg: 'rgba(255,140,0,0.15)',  border: '#ff8c00', cssClass: 'high' },
    MEDIUM:   { badge: '🟡 MEDIUM',   color: '#ffd700', light: '#ffe44d', bg: 'rgba(255,215,0,0.08)',  tagBg: 'rgba(255,215,0,0.12)',  border: '#ffd700', cssClass: 'medium' },
    LOW:      { badge: '🟢 LOW',      color: '#32cd32', light: '#55dd55', bg: 'rgba(50,205,50,0.10)',   tagBg: 'rgba(50,205,50,0.10)',  border: '#32cd32', cssClass: 'low' },
    INFO:     { badge: 'ℹ️ INFO',      color: '#1e90ff', light: '#55aaff', bg: 'rgba(30,144,255,0.08)',  tagBg: 'rgba(30,144,255,0.08)', border: '#1e90ff', cssClass: 'info' },
  };

  /* ── State ── */
  let report = null;
  let activeTab = 'overview';
  let chatMessages = [];
  let clauseFilters = { CRITICAL: true, HIGH: true, MEDIUM: true, LOW: false, INFO: false };

  /* ── DOM Refs ── */
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const els = {
    sidebar: $('#sidebar'),
    sidebarToggle: $('#sidebarToggle'),
    fileInput: $('#fileInput'),
    uploadZone: $('#uploadZone'),
    fileInfo: $('#fileInfo'),
    fileName: $('#fileName'),
    fileSize: $('#fileSize'),
    btnDemo: $('#btnDemo'),
    btnAnalyze: $('#btnAnalyze'),
    agentPanel: $('#agentPanel'),
    agentList: $('#agentList'),
    sidebarStats: $('#sidebarStats'),
    statGrid: $('#statGrid'),
    results: $('#results'),
    welcome: $('#welcome'),
    riskBanner: $('#riskBanner'),
    tabNav: $('#tabNav'),
    tabContents: $$('.tab-content'),

    // Overview
    metricScore: $('#scoreValue'),
    scoreBadge: $('#scoreBadge'),
    severityChart: $('#severityChart'),
    attentionValue: $('#attentionValue'),
    attentionBadge: $('#attentionBadge'),
    severityPills: $('#severityPills'),
    actionList: $('#actionList'),
    impactHeader: $('#impactHeader'),
    impactList: $('#impactList'),

    // Clauses
    clauseList: $('#clauseList'),
    clauseEmpty: $('#clauseEmpty'),

    // Negotiation
    negotiationList: $('#negotiationList'),
    negoEmpty: $('#negoEmpty'),
    negoDownload: $('#negoDownload'),
    btnDownloadSafer: $('#btnDownloadSafer'),

    // Chat
    chatMessages: $('#chatMessages'),
    chatInput: $('#chatInput'),
    chatSend: $('#chatSend'),
    btnClearChat: $('#btnClearChat'),

    // Footer
    btnDownloadReport: $('#btnDownloadReport'),
    footerMeta: $('#footerMeta'),
  };

  /* ═══════════════════════════════════════════════════════════════════════════
     DEMO DATA
     ═══════════════════════════════════════════════════════════════════════════ */

  const DEMO_CLAUSES = [
    {
      id: 1, section_heading: 'IP ASSIGNMENT', clause_type: 'IP_ASSIGNMENT',
      raw_text: 'Recipient hereby irrevocably assigns to Company all inventions, discoveries, and intellectual property created during this Agreement and for 1 year after, regardless of whether created on Recipient\'s own time or equipment.',
      plain_english: 'You give the company ownership of everything you create — including personal side projects on your own time and equipment — for up to a year after you leave.',
      severity: 'CRITICAL',
      risk_title: 'IP Assignment of Personal Work',
      risk_reason: 'Claims ownership of ALL creations including personal projects on personal time and equipment, extending 1 year after termination.',
      recommended_action: 'Demand a carve-out for inventions created on your own time using your own equipment.',
      safer_clause_version: 'Employee assigns to Company all inventions directly related to Company\'s business and created during working hours using Company resources. Inventions created on Employee\'s own time using personal equipment, and unrelated to Company\'s business, remain the sole property of Employee.',
      negotiation_message: 'Hi, I\'ve reviewed the IP clause and would like to request an adjustment to ensure personal projects created outside work hours remain mine. I\'ve suggested alternative wording below. Would you be open to this change? Thanks!',
      impact_scenarios: [
        'You may lose ownership of any side projects or startups you work on during employment',
        'The company could claim your open-source contributions made on weekends'
      ],
    },
    {
      id: 2, section_heading: 'ARBITRATION', clause_type: 'ARBITRATION',
      raw_text: 'All disputes shall be resolved exclusively through binding arbitration. The parties waive any right to a trial by jury and waive the right to participate in any class action.',
      plain_english: 'You give up your right to sue in court or join a class-action lawsuit. All disputes go through private arbitration instead.',
      severity: 'CRITICAL',
      risk_title: 'Mandatory Arbitration with Jury + Class Action Waiver',
      risk_reason: 'Forces disputes into private arbitration, waives your constitutional right to a jury trial, and blocks class actions — with no opt-out.',
      recommended_action: 'Add an opt-out clause for arbitration — preserve your right to go to court.',
      safer_clause_version: 'Either party may opt out of binding arbitration by providing written notice within 30 days of signing. Nothing in this section prevents participation in class actions where permitted by law.',
      negotiation_message: 'Hi, I\'ve reviewed the dispute resolution clause. I\'d like to add an opt-out option for arbitration so both parties retain the right to choose their preferred forum. I\'ve suggested language below. Does this work for you?',
      impact_scenarios: [
        'If the company violates your rights, you cannot sue them in a public court',
        'You cannot join with other affected parties in a class action — you must fight alone'
      ],
    },
    {
      id: 3, section_heading: 'NON COMPETE', clause_type: 'NON_COMPETE',
      raw_text: 'For 18 months following termination, Recipient shall not engage in any business competitive with Company, anywhere in the world.',
      plain_english: 'You cannot work for any competitor anywhere in the world for 18 months after this agreement ends — even if the company doesn\'t operate in that region.',
      severity: 'HIGH',
      risk_title: 'Worldwide Non-Compete — 18 Months',
      risk_reason: '18-month ban on working for ANY competitor worldwide with no geographic limitation tied to Company\'s actual operations.',
      recommended_action: 'Reduce duration to 12 months and limit scope to regions where Company actually does business.',
      safer_clause_version: 'For 12 months following termination, Recipient shall not provide services to direct competitors of Company within the specific metro areas where Company has active business operations.',
      negotiation_message: 'Hi, the non-compete clause is quite broad — it covers the entire world for 18 months. I\'d suggest narrowing the scope to 12 months within regions where the company actually operates. I\'ve drafted alternative language below.',
      impact_scenarios: [
        'You may be unable to work in your industry anywhere in the world for 18 months after leaving',
        'Relocating to a new city won\'t help — the restriction is global'
      ],
    },
    {
      id: 4, section_heading: 'AUTO RENEWAL', clause_type: 'AUTO_RENEWAL',
      raw_text: 'This Agreement shall automatically renew for successive 1-year terms unless either party provides written notice at least 90 days prior.',
      plain_english: 'This agreement renews automatically every year. You must give 90 days written notice to cancel — miss the deadline and you\'re locked in.',
      severity: 'MEDIUM',
      risk_title: 'Auto-Renewal with 90-Day Notice',
      risk_reason: 'Auto-renews annually. 90-day notice period is longer than standard and easy to miss.',
      recommended_action: 'Reduce notice period to 30 days or request automatic email reminders.',
      safer_clause_version: '',
      negotiation_message: '',
      impact_scenarios: [],
    },
    {
      id: 5, section_heading: 'CONFIDENTIALITY', clause_type: 'NDA',
      raw_text: 'Recipient agrees to hold all Confidential Information in strict confidence.',
      plain_english: 'You must keep the company\'s confidential information secret and only use it as authorized.',
      severity: 'LOW',
      risk_title: 'Standard Confidentiality Obligation',
      risk_reason: 'Standard NDA language requiring reasonable care — no unusual provisions.',
      recommended_action: 'No action needed — standard boilerplate.',
      safer_clause_version: '',
      negotiation_message: '',
      impact_scenarios: [],
    },
    {
      id: 6, section_heading: 'GOVERNING LAW', clause_type: 'GOVERNING_LAW',
      raw_text: 'This Agreement shall be governed by the laws of the State of New York.',
      plain_english: 'This agreement is governed by New York law, and disputes must be handled in New York courts.',
      severity: 'LOW',
      risk_title: 'Standard Governing Law',
      risk_reason: 'Standard choice-of-law clause selecting New York — common in contracts.',
      recommended_action: 'No action needed unless you are far from New York.',
      safer_clause_version: '',
      negotiation_message: '',
      impact_scenarios: [],
    },
    {
      id: 7, section_heading: 'ENTIRE AGREEMENT', clause_type: 'OTHER',
      raw_text: 'This Agreement constitutes the entire agreement between the parties.',
      plain_english: 'This document is the complete and final agreement between you and the company.',
      severity: 'INFO',
      risk_title: 'Standard Entire Agreement Clause',
      risk_reason: 'Standard integration clause confirming this is the complete agreement.',
      recommended_action: 'No action needed — standard boilerplate.',
      safer_clause_version: '',
      negotiation_message: '',
      impact_scenarios: [],
    },
  ];

  function buildReport(clauses) {
    const crit = clauses.filter(c => c.severity === 'CRITICAL').length;
    const high = clauses.filter(c => c.severity === 'HIGH').length;
    const med  = clauses.filter(c => c.severity === 'MEDIUM').length;
    const low  = clauses.filter(c => c.severity === 'LOW').length;
    const raw  = (crit * 10 + high * 7 + med * 4 + low * 1) / clauses.length;
    const overall = Math.min(Math.round(raw * 10) / 10, 10.0);

    return {
      contract_name: 'sample_nda.txt (Demo)',
      generated_at: new Date(),
      summary: {
        total_clauses: clauses.length,
        critical_count: crit,
        high_count: high,
        medium_count: med,
        low_count: low,
        overall_score: overall,
        contract_type: 'NDA',
      },
      top_3_actions: [
        'Demand a carve-out for inventions created on your own time using your own equipment.',
        'Add an opt-out clause for arbitration — preserve your right to go to court.',
        'Reduce non-compete to 12 months with geographic scope tied to actual operations.',
      ],
      scored_clauses: clauses,
      markdown_report: '',
    };
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     UTILITIES
     ═══════════════════════════════════════════════════════════════════════════ */

  function formatDate(d) {
    const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    const h = String(d.getHours()).padStart(2, '0');
    const m = String(d.getMinutes()).padStart(2, '0');
    return `${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()} at ${h}:${m}`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
      btn.textContent = 'Copied!';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
    }).catch(() => {
      btn.textContent = 'Error';
      setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     SIDEBAR TOGGLE
     ═══════════════════════════════════════════════════════════════════════════ */

  els.sidebarToggle.addEventListener('click', () => {
    els.sidebar.classList.toggle('collapsed');
  });

  /* ═══════════════════════════════════════════════════════════════════════════
     FILE UPLOAD
     ═══════════════════════════════════════════════════════════════════════════ */

  let uploadedFile = null;

  els.uploadZone.addEventListener('click', () => els.fileInput.click());

  els.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
  });

  els.uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    els.uploadZone.classList.add('dragover');
  });

  els.uploadZone.addEventListener('dragleave', () => {
    els.uploadZone.classList.remove('dragover');
  });

  els.uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    els.uploadZone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  function handleFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = ['pdf', 'txt', 'docx'];
    if (!allowed.includes(ext)) {
      alert('Unsupported file type. Please upload PDF, TXT, or DOCX files.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert(`File too large (${(file.size/1024/1024).toFixed(1)}MB). Maximum is 10MB.`);
      return;
    }
    uploadedFile = file;
    els.fileInfo.style.display = 'flex';
    els.fileName.textContent = file.name;
    els.fileSize.textContent = `${(file.size/1024).toFixed(1)} KB`;
    els.btnAnalyze.disabled = false;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     AGENT PIPELINE SIMULATION
     ═══════════════════════════════════════════════════════════════════════════ */

  const AGENTS = ['Extractor', 'Classifier', 'Risk Scorer', 'Translator', 'Reporter'];

  function resetAgents() {
    els.agentPanel.style.display = 'block';
    const rows = els.agentList.querySelectorAll('.agent-row');
    rows.forEach(r => {
      r.querySelector('.agent-status').className = 'agent-status pending';
      r.querySelector('.agent-status').textContent = '⏳';
      r.querySelector('.agent-msg').textContent = 'Pending';
    });
  }

  function setAgentStatus(name, status, msg) {
    const row = els.agentList.querySelector(`[data-agent="${name}"]`);
    if (!row) return;
    const statusEl = row.querySelector('.agent-status');
    const msgEl = row.querySelector('.agent-msg');
    const iconMap = { running: '⚙️', completed: '✅', failed: '❌', pending: '⏳' };
    statusEl.className = `agent-status ${status}`;
    statusEl.textContent = iconMap[status] || '⏳';
    msgEl.textContent = msg || status.charAt(0).toUpperCase() + status.slice(1);
  }

  function simulatePipeline(clauses, callback) {
    resetAgents();
    let step = 0;

    function next() {
      if (step >= AGENTS.length) {
        setTimeout(() => callback(buildReport(clauses)), 300);
        return;
      }
      const agent = AGENTS[step];
      setAgentStatus(agent, 'running', 'Working...');
      setTimeout(() => {
        setAgentStatus(agent, 'completed', 'OK');
        step++;
        next();
      }, 600 + Math.random() * 500);
    }

    setAgentStatus(AGENTS[0], 'running', 'Working...');
    setTimeout(() => {
      setAgentStatus(AGENTS[0], 'completed', 'OK');
      step = 1;
      next();
    }, 600);
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     RENDER ALL
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderAll() {
    if (!report) return;
    renderRiskBanner();
    renderSidebarStats();
    renderOverview();
    renderClauses();
    renderNegotiation();
    renderChatWelcome();
    renderFooter();
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     RISK BANNER
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderRiskBanner() {
    const s = report.summary;
    const totalRisky = s.critical_count + s.high_count;
    if (totalRisky === 0) {
      els.riskBanner.style.display = 'none';
      return;
    }
    els.riskBanner.style.display = 'flex';

    let type, emoji, text;
    if (s.critical_count >= 2) {
      type = 'critical';
      emoji = '🚨';
      text = `This contract contains <b>${totalRisky} HIGH-RISK clauses</b> — including <b>${s.critical_count} critical</b>. Do <u>not</u> sign without renegotiation.`;
    } else if (s.high_count >= 2) {
      type = 'warning';
      emoji = '⚠️';
      text = `This contract has <b>${totalRisky} high-risk clauses</b>. Review carefully before signing.`;
    } else {
      type = 'caution';
      emoji = '⚡';
      text = `Found <b>${totalRisky} concerning clauses</b>. Check the details below before signing.`;
    }

    els.riskBanner.className = `risk-banner ${type}`;
    els.riskBanner.innerHTML = `<span class="risk-banner-icon">${emoji}</span><span>${text}</span>`;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     SIDEBAR STATS
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderSidebarStats() {
    els.sidebarStats.style.display = 'block';
    const s = report.summary;
    const infoCount = s.total_clauses - s.critical_count - s.high_count - s.medium_count - s.low_count;
    els.statGrid.innerHTML = `
      <div class="stat-item full">
        <div class="stat-item-label">Overall Risk Score</div>
        <div class="stat-item-value score">${s.overall_score}/10</div>
      </div>
      <div class="stat-item">
        <div class="stat-item-label">🔴 Critical</div>
        <div class="stat-item-value critical">${s.critical_count}</div>
      </div>
      <div class="stat-item">
        <div class="stat-item-label">🟠 High</div>
        <div class="stat-item-value high">${s.high_count}</div>
      </div>
      <div class="stat-item">
        <div class="stat-item-label">🟡 Medium</div>
        <div class="stat-item-value medium">${s.medium_count}</div>
      </div>
      <div class="stat-item">
        <div class="stat-item-label">🟢 Low</div>
        <div class="stat-item-value low">${s.low_count}</div>
      </div>
      <div class="stat-item full" style="margin-top:0.25rem">
        <span style="font-size:0.72rem;color:#606878">${s.contract_type} · ${s.total_clauses} clauses</span>
      </div>
      <div class="stat-item full" style="padding:0.35rem">
        <span style="font-size:0.7rem;color:#606878">ℹ️ ${infoCount} info</span>
      </div>
    `;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     OVERVIEW TAB
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderOverview() {
    const s = report.summary;

    // Risk score
    const score = s.overall_score;
    let scColor, scLabel, scBadge;
    if (score >= 7) {
      scColor = '#ff4444'; scLabel = 'HIGH RISK'; scBadge = 'danger';
    } else if (score >= 4) {
      scColor = '#ff8c00'; scLabel = 'MODERATE'; scBadge = 'warning';
    } else {
      scColor = '#32cd32'; scLabel = 'LOW RISK'; scBadge = 'success';
    }
    els.metricScore.innerHTML = `${score}<span class="unit">/10</span>`;
    els.metricScore.style.color = scColor;
    els.scoreBadge.textContent = scLabel;
    els.scoreBadge.className = `metric-badge ${scBadge}`;

    // Attention metric
    const risky = s.critical_count + s.high_count + s.medium_count;
    const pct = s.total_clauses > 0 ? (risky / s.total_clauses * 100) : 0;
    let attColor, attBadge;
    if (pct >= 50) { attColor = '#ff4444'; attBadge = 'danger'; }
    else if (pct >= 25) { attColor = '#ff8c00'; attBadge = 'warning'; }
    else { attColor = '#32cd32'; attBadge = 'success'; }
    els.attentionValue.innerHTML = `${risky}<span class="unit">/${s.total_clauses}</span>`;
    els.attentionValue.style.color = attColor;
    els.attentionBadge.textContent = `${Math.round(pct)}% of clauses`;
    els.attentionBadge.className = `metric-badge ${attBadge}`;

    // Bar chart
    drawBarChart(s);

    // Severity pills
    const infoCount = s.total_clauses - s.critical_count - s.high_count - s.medium_count - s.low_count;
    els.severityPills.innerHTML = `
      <div class="severity-pill">
        <div class="severity-pill-label">🔴 Critical</div>
        <div class="severity-pill-value critical">${s.critical_count}</div>
      </div>
      <div class="severity-pill">
        <div class="severity-pill-label">🟠 High</div>
        <div class="severity-pill-value high">${s.high_count}</div>
      </div>
      <div class="severity-pill">
        <div class="severity-pill-label">🟡 Medium</div>
        <div class="severity-pill-value medium">${s.medium_count}</div>
      </div>
      <div class="severity-pill">
        <div class="severity-pill-label">🟢 Low</div>
        <div class="severity-pill-value low">${s.low_count}</div>
      </div>
      <div class="severity-pill">
        <div class="severity-pill-label">ℹ️ Info</div>
        <div class="severity-pill-value info">${infoCount}</div>
      </div>
    `;

    // Top 3 actions
    const colors = ['#ff4444', '#ff8c00', '#ffd700'];
    const nums = ['①', '②', '③'];
    els.actionList.innerHTML = report.top_3_actions.map((a, i) => `
      <div class="action-item">
        <span class="action-num">${nums[i]}</span>
        <span class="action-text">${escapeHtml(a)}</span>
      </div>
    `).join('');

    // Impact scenarios
    const criticals = report.scored_clauses.filter(c => c.severity === 'CRITICAL');
    if (criticals.length === 0) {
      els.impactHeader.style.display = 'none';
      els.impactList.innerHTML = '';
      return;
    }
    els.impactHeader.style.display = '';
    els.impactList.innerHTML = criticals.slice(0, 3).map(c => `
      <div class="impact-group">
        <div class="impact-group-title">${escapeHtml(c.risk_title)}</div>
        ${(c.impact_scenarios || []).map(is => `<div class="impact-item">▸ ${escapeHtml(is)}</div>`).join('')}
      </div>
    `).join('');
  }

  function drawBarChart(s) {
    const canvas = els.severityChart;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const w = rect.width;
    const h = rect.height;
    ctx.clearRect(0, 0, w, h);

    const data = [
      { label: 'Critical', count: s.critical_count, color: '#ff4444' },
      { label: 'High', count: s.high_count, color: '#ff8c00' },
      { label: 'Medium', count: s.medium_count, color: '#ffd700' },
      { label: 'Low', count: s.low_count, color: '#32cd32' },
    ];

    const maxVal = Math.max(...data.map(d => d.count), 1);
    const barWidth = (w - 80) / data.length;
    const chartH = h - 40;
    const padding = 30;

    data.forEach((d, i) => {
      const barH = (d.count / maxVal) * (chartH - 10);
      const x = padding + i * barWidth + barWidth * 0.15;
      const y = chartH - barH + 5;

      ctx.fillStyle = d.color;
      ctx.beginPath();
      const r = 4;
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + barWidth * 0.7 - r, y);
      ctx.quadraticCurveTo(x + barWidth * 0.7, y, x + barWidth * 0.7, y + r);
      ctx.lineTo(x + barWidth * 0.7, chartH + 5);
      ctx.lineTo(x, chartH + 5);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.fill();

      ctx.fillStyle = '#9aa0ab';
      ctx.font = '10px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(d.count, x + barWidth * 0.35, y - 6);

      ctx.fillStyle = '#606878';
      ctx.font = '9px Inter, sans-serif';
      ctx.fillText(d.label.substring(0, 4), x + barWidth * 0.35, chartH + 22);
    });

    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.beginPath();
    ctx.moveTo(padding, chartH + 5);
    ctx.lineTo(w - padding, chartH + 5);
    ctx.stroke();
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     CLAUSES TAB
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderClauses() {
    const visible = report.scored_clauses.filter(c => clauseFilters[c.severity] !== false);
    els.clauseEmpty.style.display = visible.length === 0 ? '' : 'none';
    els.clauseList.innerHTML = visible.map(c => renderClauseCard(c)).join('');
    attachClauseEvents();
  }

  function renderClauseCard(c) {
    const sev = SEV[c.severity];
    const tags = `
      <span class="severity-badge ${sev.cssClass}">${c.severity}</span>
      <span class="clause-tag type">#${escapeHtml(c.clause_type)}</span>
      <span style="color:#606878;font-size:0.75rem">Clause #${c.id} · ${escapeHtml(c.section_heading || '—')}</span>
    `;

    const analysisHtml = `
      <div class="clause-analysis">
        ${c.plain_english ? `
          <div class="info-card plain">
            <div class="info-card-title">💬 What This Means</div>
            <div class="info-card-content">${escapeHtml(c.plain_english)}</div>
          </div>
        ` : ''}
        <div class="info-card risk">
          <div class="info-card-title">⚠️ Why This Is Risky</div>
          <div class="info-card-content">${escapeHtml(c.risk_reason)}</div>
        </div>
        ${c.recommended_action ? `
          <div class="info-card fix">
            <div class="info-card-title">✅ How to Fix It</div>
            <div class="info-card-content">${escapeHtml(c.recommended_action)}</div>
          </div>
        ` : ''}
        ${(c.impact_scenarios && c.impact_scenarios.length > 0) ? `
          <div class="info-card impact">
            <div class="info-card-title">🌪️ What Could Happen</div>
            <div class="info-card-content">${c.impact_scenarios.map(is => `▸ ${escapeHtml(is)}`).join('<br>')}</div>
          </div>
        ` : ''}
      </div>
    `;

    const safer = c.safer_clause_version || generateFallbackSafer(c);
    const negMsg = c.negotiation_message || generateFallbackMessage(c);

    return `
      <div class="clause-card ${sev.cssClass}" data-clause-id="${c.id}">
        <div class="clause-card-header">
          <span class="expand-icon">▶</span>
          <span class="severity-badge ${sev.cssClass}">${sev.badge}</span>
          <span class="clause-card-title">${escapeHtml(c.risk_title)}</span>
          <span class="clause-card-meta">#${c.id}</span>
        </div>
        <div class="clause-card-body">
          <div class="clause-tags">${tags}</div>
          <div class="clause-original-text">${escapeHtml(c.raw_text)}</div>
          ${analysisHtml}
          ${safer ? `
            <div class="code-block-label">💡 Suggested Wording</div>
            <div class="code-block">
              <button class="code-block-copy" data-text="${escapeHtml(safer)}">Copy</button>
              ${escapeHtml(safer)}
            </div>
          ` : ''}
          <div class="code-block-label">📧 What to Say (Negotiation Message)</div>
          <div class="code-block">
            <button class="code-block-copy" data-text="${escapeHtml(negMsg)}">Copy</button>
            ${escapeHtml(negMsg)}
          </div>
          <div class="clause-ai-btn-row">
            <button class="btn btn-secondary btn-sm btn-ask-ai" data-clause-id="${c.id}">🤖 Ask AI about this clause</button>
          </div>
          <div class="ai-response" data-ai-clause="${c.id}" style="display:none"></div>
        </div>
      </div>
    `;
  }

  function attachClauseEvents() {
    $$('.clause-card-header').forEach(header => {
      header.addEventListener('click', () => {
        header.parentElement.classList.toggle('expanded');
      });
    });

    $$('.code-block-copy').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(btn.dataset.text, btn);
      });
    });

    $$('.btn-ask-ai').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const clauseId = parseInt(btn.dataset.clauseId);
        const clause = report.scored_clauses.find(c => c.id === clauseId);
        if (clause) {
          const prompt = `Tell me more about the ${clause.risk_title} clause. Why is it dangerous and what should I do?`;
          askAiInline(clauseId, prompt);
        }
      });
    });

    // Open critical/high by default
    $$('.clause-card').forEach(card => {
      if (card.classList.contains('critical') || card.classList.contains('high')) {
        card.classList.add('expanded');
      }
    });
  }

  function askAiInline(clauseId, prompt) {
    const respDiv = document.querySelector(`.ai-response[data-ai-clause="${clauseId}"]`);
    if (!respDiv) return;
    respDiv.style.display = 'block';
    respDiv.innerHTML = `
      <div class="ai-response-title">🤖 AI Response</div>
      <div class="ai-response-text">Thinking...</div>
    `;
    const clause = report.scored_clauses.find(c => c.id === clauseId);
    if (!clause) return;

    if (useServer) {
      fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: chatContext, history: [], message: prompt }),
      }).then(r => r.json()).then(data => {
        respDiv.innerHTML = `
          <div class="ai-response-title">🤖 AI Response</div>
          <div class="ai-response-text">${escapeHtml(data.response || 'No response.')}</div>
        `;
      }).catch(() => {
        respDiv.innerHTML = `
          <div class="ai-response-title">🤖 AI Response</div>
          <div class="ai-response-text">Sorry, the AI is unavailable right now.</div>
        `;
      });
    } else {
      setTimeout(() => {
        const responses = [
          `This clause is risky because ${clause.risk_reason.toLowerCase()} I recommend you ${clause.recommended_action.toLowerCase()} If you sign as-is, ${(clause.impact_scenarios || ['you may face consequences'])[0].toLowerCase()}`,
          `Looking at this more closely, the key issue is that ${clause.risk_reason.toLowerCase().split('.')[0]}. The safest approach would be to ${clause.recommended_action.toLowerCase()}`,
        ];
        respDiv.innerHTML = `
          <div class="ai-response-title">🤖 AI Response</div>
          <div class="ai-response-text">${escapeHtml(responses[Math.floor(Math.random() * responses.length)])}</div>
        `;
      }, 1200 + Math.random() * 800);
    }
  }

  function generateFallbackSafer(c) {
    const fallbacks = {
      IP_ASSIGNMENT: 'Employee assigns only inventions directly related to Company\'s business, created during working hours using Company resources. Personal projects remain Employee\'s property.',
      ARBITRATION: 'Either party may opt out of arbitration within 30 days. Both parties retain the right to bring claims in court.',
      NON_COMPETE: 'Non-compete limited to 12 months within specific metro areas where Company operates.',
      AUTO_RENEWAL: 'Agreement renews only with mutual written consent. No automatic renewal.',
      TERMINATION: 'Either party may terminate with 30 days written notice.',
      INDEMNIFICATION: 'Indemnification limited to direct damages caused by negligence or willful misconduct.',
      LIABILITY_CAP: 'Liability capped at the greater of fees paid or $10,000.',
      DATA_SHARING: 'Data shared only with explicit opt-in consent, revocable at any time.',
      GOVERNING_LAW: 'Governing law set to user\'s home state with optional mediation.',
      PAYMENT: 'Payment due net-30 after invoice receipt. Late fees capped at 5% annually.',
    };
    return fallbacks[c.clause_type] || 'Request a mutual agreement: both parties share rights and obligations equally. Remove one-sided provisions.';
  }

  function generateFallbackMessage(c) {
    const topic = c.section_heading || c.clause_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    const safer = c.safer_clause_version || generateFallbackSafer(c);
    return `Hi,\n\nI've reviewed the contract and would like to discuss the ${topic} clause. I'd suggest the following adjustment:\n\n'${safer}'\n\nThis ensures both parties are treated fairly. Would you be open to this change?\n\nThanks!`;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     NEGOTIATION TAB
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderNegotiation() {
    const highRisk = report.scored_clauses.filter(c => c.severity === 'CRITICAL' || c.severity === 'HIGH');
    els.negoEmpty.style.display = highRisk.length === 0 ? '' : 'none';
    els.negoDownload.style.display = highRisk.length > 0 ? '' : 'none';

    if (highRisk.length === 0) {
      els.negotiationList.innerHTML = '';
      return;
    }

    els.negotiationList.innerHTML = highRisk.map((c, i) => {
      const sev = SEV[c.severity];
      const safer = c.safer_clause_version || generateFallbackSafer(c);
      const negMsg = c.negotiation_message || generateFallbackMessage(c);
      return `
        <div class="negotiation-item">
          <div class="negotiation-item-title">${sev.badge}  ${escapeHtml(c.risk_title)}</div>
          <div class="negotiation-compare">
            <div class="nego-card original">
              <div class="nego-card-label">⚠️ Original Clause</div>
              <div class="nego-card-text">${escapeHtml(c.raw_text.substring(0, 500))}</div>
            </div>
            <div class="nego-card safer">
              <div class="nego-card-label">✅ Safer Alternative</div>
              <div class="nego-card-text">${escapeHtml(safer)}</div>
            </div>
          </div>
          <div class="code-block-label">📧 Negotiation Message</div>
          <div class="code-block">
            <button class="code-block-copy" data-text="${escapeHtml(negMsg)}">Copy</button>
            ${escapeHtml(negMsg)}
          </div>
          ${(c.impact_scenarios && c.impact_scenarios.length > 0) ? `
            <div class="nego-impact">
              <div class="nego-impact-title">⚠️ If you don't negotiate this...</div>
              ${c.impact_scenarios.map(is => `<div class="impact-item">▸ ${escapeHtml(is)}</div>`).join('')}
            </div>
          ` : ''}
          ${i < highRisk.length - 1 ? '<hr class="nego-divider">' : ''}
        </div>
      `;
    }).join('');

    // Attach copy events
    els.negotiationList.querySelectorAll('.code-block-copy').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(btn.dataset.text, btn);
      });
    });
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     CHAT TAB
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderChatWelcome() {
    chatMessages = [];
    const s = report.summary;
    const totalRisky = s.critical_count + s.high_count;
    let welcome;
    if (totalRisky > 0) {
      welcome = `I've analyzed your contract and found **${totalRisky} high-risk clause(s)** (score: **${s.overall_score}/10**).\n\nYou can ask me to:\n- 🔍 Explain any clause in simple terms\n- 🛡️ Tell you which clauses are risky and why\n- ✏️ Suggest safer wording for specific clauses\n- 📧 Help you draft a negotiation message\n- ⚠️ Describe what could happen if you sign as-is\n\nWhat would you like to know?`;
    } else {
      welcome = `I've analyzed your contract and it looks reasonable (score: **${s.overall_score}/10**). You can ask me to explain any clause or check for potential issues. What would you like to know?`;
    }
    chatMessages = [{ role: 'assistant', content: welcome }];
    renderChatMessages();
    els.btnClearChat.style.display = 'none';
  }

  function renderChatMessages() {
    els.chatMessages.innerHTML = chatMessages.map(m => `
      <div class="chat-msg ${m.role}">
        <div class="chat-avatar">${m.role === 'assistant' ? '🤖' : '👤'}</div>
        <div class="chat-bubble">${formatChatText(m.content)}</div>
      </div>
    `).join('');
    els.chatMessages.scrollTop = els.chatMessages.scrollHeight;
    els.btnClearChat.style.display = chatMessages.length > 1 ? '' : 'none';
  }

  function formatChatText(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  function sendChatMessage(content) {
    if (!content.trim()) return;
    chatMessages.push({ role: 'user', content: content.trim() });
    renderChatMessages();
    els.chatInput.value = '';

    chatMessages.push({ role: 'assistant', content: 'Thinking...' });
    renderChatMessages();

    if (useServer) {
      const history = chatMessages.slice(0, -1).map(m => ({ role: m.role, content: m.content }));
      fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: chatContext, history: history, message: content.trim() }),
      }).then(r => r.json()).then(data => {
        chatMessages[chatMessages.length - 1] = { role: 'assistant', content: data.response || 'No response.' };
        renderChatMessages();
      }).catch(() => {
        chatMessages[chatMessages.length - 1] = { role: 'assistant', content: 'Sorry, the AI is unavailable. Try again later.' };
        renderChatMessages();
      });
    } else {
      setTimeout(() => {
        const response = generateMockResponse(content);
        chatMessages[chatMessages.length - 1] = { role: 'assistant', content: response };
        renderChatMessages();
      }, 1000 + Math.random() * 1500);
    }
  }

  function generateMockResponse(prompt) {
    const lower = prompt.toLowerCase();
    const s = report.summary;
    const criticals = report.scored_clauses.filter(c => c.severity === 'CRITICAL');

    if (lower.includes('fix') || lower.includes('change') || lower.includes('request')) {
      return `Based on my analysis, the **most important changes** you should request are:\n\n**1. Fix the IP Assignment clause** — Demand a carve-out for personal projects created on your own time. The current clause could let the company claim ownership of your side projects.\n\n**2. Add Arbitration Opt-Out** — The mandatory arbitration clause waives your right to go to court. Request a 30-day opt-out window.\n\n**3. Narrow the Non-Compete** — Reduce from 18 months worldwide to 12 months within the company's actual operating regions.\n\nWould you like me to draft the specific language for any of these?`;
    }
    if (lower.includes('safe') || lower.includes('risk') || lower.includes('worst')) {
      return `This contract has a risk score of **${s.overall_score}/10**, which is **${s.overall_score >= 7 ? 'HIGH RISK' : s.overall_score >= 4 ? 'MODERATE' : 'LOW RISK'}**. I would ${s.overall_score >= 4 ? 'NOT recommend' : 'cautiously say it is okay to'} sign this as-is.\n\nThe **worst that could happen**:\n\n${criticals.length > 0 ? criticals.map(c => `- ${(c.impact_scenarios || ['Significant risk'])[0]}`).join('\n') : '- No critical issues detected.'}\n\nI recommend addressing the critical items before signing.`;
    }
    if (lower.includes('summar') || lower.includes('summary') || lower.includes('biggest')) {
      const topRisks = report.scored_clauses.filter(c => c.severity === 'CRITICAL' || c.severity === 'HIGH').slice(0, 3);
      if (topRisks.length === 0) return 'Great news — there are no critical or high-risk clauses in this contract. The overall risk score is low, suggesting this is a reasonable agreement.';
      return `Here are the **top ${topRisks.length} risks** I found:\n\n${topRisks.map((c, i) => `**${i + 1}. ${c.risk_title}** (${c.severity}): ${c.recommended_action}`).join('\n\n')}\n\nAddress these before signing.`;
    }
    if (lower.includes('ip') || lower.includes('intellectual') || lower.includes('assign')) {
      const ipClause = report.scored_clauses.find(c => c.clause_type === 'IP_ASSIGNMENT');
      if (ipClause) return `The IP Assignment clause is **${ipClause.severity}**. ${ipClause.risk_reason} **My recommendation**: ${ipClause.recommended_action}\n\nSuggested safer wording:\n"${ipClause.safer_clause_version || generateFallbackSafer(ipClause)}"`;
    }
    if (lower.includes('arbitration') || lower.includes('dispute') || lower.includes('jury')) {
      const arbClause = report.scored_clauses.find(c => c.clause_type === 'ARBITRATION');
      if (arbClause) return `The Arbitration clause is **${arbClause.severity}**. ${arbClause.risk_reason} **My recommendation**: ${arbClause.recommended_action}`;
    }
    return `I've analyzed all ${s.total_clauses} clauses in this ${s.contract_type}. The overall risk score is **${s.overall_score}/10** with ${s.critical_count} critical, ${s.high_count} high, and ${s.medium_count} medium-risk items. You can ask me about any specific clause or risk — I'm here to help!`;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     FOOTER
     ═══════════════════════════════════════════════════════════════════════════ */

  function renderFooter() {
    const s = report.summary;
    els.footerMeta.textContent = `Generated ${formatDate(report.generated_at)} · ${s.contract_type} · ${s.total_clauses} clauses · Score: ${s.overall_score}/10`;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     DOWNLOAD
     ═══════════════════════════════════════════════════════════════════════════ */

  els.btnDownloadReport.addEventListener('click', () => {
    if (!report) return;
    const lines = [];
    lines.push(`# ClauseGuard Risk Analysis Report`);
    lines.push(`# Contract: ${report.contract_name}`);
    lines.push(`# Generated: ${formatDate(report.generated_at)}`);
    lines.push(`# Score: ${report.summary.overall_score}/10 | Type: ${report.summary.contract_type}`);
    lines.push('');
    report.scored_clauses.forEach(c => {
      lines.push(`## ${c.severity} — ${c.risk_title}`);
      lines.push(`**Original:** ${c.raw_text}`);
      if (c.plain_english) lines.push(`**Translation:** ${c.plain_english}`);
      lines.push(`**Risk:** ${c.risk_reason}`);
      if (c.recommended_action) lines.push(`**Action:** ${c.recommended_action}`);
      if (c.safer_clause_version) lines.push(`**Safer:** ${c.safer_clause_version}`);
      lines.push('');
    });
    downloadFile(lines.join('\n'), `clauseguard_report_${report.contract_name.replace('.', '_')}.md`, 'text/markdown');
  });

  els.btnDownloadSafer.addEventListener('click', () => {
    if (!report) return;
    const lines = [];
    lines.push(`# SAFER VERSION — ${report.contract_name}`);
    lines.push(`# Auto-generated by ClauseGuard — replaces ${report.summary.critical_count + report.summary.high_count} high-risk clauses`);
    lines.push(`# Original risk score: ${report.summary.overall_score}/10`);
    lines.push('');
    report.scored_clauses.forEach((c, i) => {
      const safer = c.safer_clause_version || generateFallbackSafer(c);
      const sev = c.severity;
      if (safer && (sev === 'CRITICAL' || sev === 'HIGH')) {
        lines.push(`# ── Replaced: ${sev} Risk — ${c.risk_title} ──`);
        lines.push(`# Original:`);
        c.raw_text.split('\n').forEach(l => lines.push(`#   ${l.trim()}`));
        lines.push('');
        lines.push(`${i + 1}. ${c.section_heading || 'CLAUSE'}. ${safer}`);
        lines.push('');
      } else {
        lines.push(`${i + 1}. ${c.section_heading || 'CLAUSE'}. ${c.raw_text.trim()}`);
        lines.push('');
      }
    });
    downloadFile(lines.join('\n'), `safer_${report.contract_name}`, 'text/plain');
  });

  function downloadFile(content, filename, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     TAB SWITCHING
     ═══════════════════════════════════════════════════════════════════════════ */

  els.tabNav.addEventListener('click', (e) => {
    const btn = e.target.closest('.tab-btn');
    if (!btn) return;
    const tab = btn.dataset.tab;
    if (tab === activeTab) return;
    activeTab = tab;
    els.tabNav.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    els.tabContents.forEach(tc => {
      tc.classList.toggle('active', tc.id === `tab-${tab}`);
    });
    if (tab === 'clauses') renderClauses();
    if (tab === 'negotiation') renderNegotiation();
    if (tab === 'chat' && chatMessages.length === 0) renderChatWelcome();
  });

  /* ═══════════════════════════════════════════════════════════════════════════
     CLAUSE FILTERS
     ═══════════════════════════════════════════════════════════════════════════ */

  document.querySelector('.filter-bar').addEventListener('change', (e) => {
    if (e.target.type !== 'checkbox') return;
    const chip = e.target.closest('.filter-chip');
    if (!chip) return;
    const sev = chip.dataset.sev;
    clauseFilters[sev] = e.target.checked;
    if (activeTab === 'clauses') renderClauses();
  });

  /* ═══════════════════════════════════════════════════════════════════════════
     CHAT HANDLERS
     ═══════════════════════════════════════════════════════════════════════════ */

  els.chatSend.addEventListener('click', () => {
    sendChatMessage(els.chatInput.value);
  });

  els.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage(els.chatInput.value);
    }
  });

  els.btnClearChat.addEventListener('click', () => {
    renderChatWelcome();
  });

  $$('.chip-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      sendChatMessage(btn.dataset.prompt);
    });
  });

  /* ═══════════════════════════════════════════════════════════════════════════
     DEMO BUTTON
     ═══════════════════════════════════════════════════════════════════════════ */

  els.btnDemo.addEventListener('click', async () => {
    els.btnDemo.disabled = true;
    els.btnDemo.textContent = '⚙️ Loading Demo...';
    els.btnAnalyze.disabled = true;

    if (useServer) {
      try {
        const res = await fetch(`${API_BASE}/api/demo`);
        if (res.ok) {
          const data = await res.json();
          report = data;
          finishLoad();
          return;
        }
      } catch (_) { /* fall back to mock */ }
    }

    simulatePipeline(DEMO_CLAUSES, (r) => {
      report = r;
      finishLoad();
    });
  });

  function finishLoad() {
    els.btnDemo.disabled = false;
    els.btnDemo.innerHTML = '<span class="btn-icon">⚡</span> Instant Demo';
    els.btnAnalyze.disabled = !uploadedFile;
    els.welcome.style.display = 'none';
    els.results.style.display = 'block';
    els.sidebarStats.style.display = 'block';
    activeTab = 'overview';
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    const overviewBtn = document.querySelector('[data-tab="overview"]');
    if (overviewBtn) overviewBtn.classList.add('active');
    els.tabContents.forEach(tc => tc.classList.remove('active'));
    const overviewTab = document.getElementById('tab-overview');
    if (overviewTab) overviewTab.classList.add('active');
    if (useServer) buildChatContext();
    renderAll();
  }

  async function buildChatContext() {
    try {
      const res = await fetch(`${API_BASE}/api/build-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_text: '',
          report: report,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        chatContext = data.context || '';
      }
    } catch (_) {
      chatContext = '';
    }
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     ANALYZE BUTTON (mock — calls same demo pipeline for now)
     ═══════════════════════════════════════════════════════════════════════════ */

  els.btnAnalyze.addEventListener('click', async () => {
    if (!uploadedFile) return;
    els.btnAnalyze.disabled = true;
    els.btnAnalyze.innerHTML = '<span class="btn-icon">⚙️</span> Analyzing...';
    els.btnDemo.disabled = true;

    if (useServer) {
      try {
        resetAgents();
        els.agentPanel.style.display = 'block';
        pollAgentStatus();

        const formData = new FormData();
        formData.append('file', uploadedFile);
        const res = await fetch(`${API_BASE}/api/analyze`, { method: 'POST', body: formData });
        if (res.ok) {
          stopPolling();
          report = await res.json();
          finishLoad();
          return;
        }
        const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
        stopPolling();
        alert(`Analysis failed: ${err.detail || 'Unknown error'}`);
      } catch (e) {
        stopPolling();
        alert(`Could not reach server: ${e.message}`);
      }
    }

    simulatePipeline(DEMO_CLAUSES, (r) => {
      r.contract_name = uploadedFile.name;
      report = r;
      finishLoad();
    });
  });

  let pollTimer = null;
  function pollAgentStatus() {
    fetch(`${API_BASE}/api/agent-status`)
      .then(r => r.json())
      .then(data => {
        for (const [agent, info] of Object.entries(data)) {
          setAgentStatus(agent, info.status, info.message);
        }
      })
      .catch(() => {});
    pollTimer = setTimeout(pollAgentStatus, 800);
  }
  function stopPolling() {
    if (pollTimer) { clearTimeout(pollTimer); pollTimer = null; }
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     WINDOW RESIZE — redraw chart
     ═══════════════════════════════════════════════════════════════════════════ */

  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      if (report && activeTab === 'overview') {
        drawBarChart(report.summary);
      }
    }, 200);
  });

  /* ═══════════════════════════════════════════════════════════════════════════
     INIT
     ═══════════════════════════════════════════════════════════════════════════ */

  checkServer().then(available => {
    if (available) {
      console.log('🛡️ ClauseGuard ready — connected to backend server.');
      console.log('→ Click "Instant Demo" or upload + "Analyze Contract" for AI-powered analysis.');
    } else {
      console.log('🛡️ ClauseGuard ready — running in offline/demo mode.');
      console.log('→ Click "Instant Demo" to see a pre-analyzed report.');
      console.log('→ Or upload a contract file and click "Analyze Contract".');
      console.log('→ Start the server with: python server.py');
    }
  });

})();
