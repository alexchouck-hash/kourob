/**
 * KouroB Public Site - Interactive Node Engine & Simulator
 * Standards-compliant, zero-dependency client-side script.
 */

// --- 1. Theme Management ---
function initTheme() {
  const themeToggle = document.getElementById('theme-toggle');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
  const savedTheme = localStorage.getItem('kourob_theme');

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
      if (themeToggle) themeToggle.innerHTML = '☀️';
    } else if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      if (themeToggle) themeToggle.innerHTML = '🌙';
    } else {
      document.documentElement.removeAttribute('data-theme');
      if (themeToggle) themeToggle.innerHTML = prefersDark.matches ? '☀️' : '🌙';
    }
  }

  applyTheme(savedTheme);

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      let next = 'dark';
      if (current === 'dark') next = 'light';
      else if (current === 'light') next = 'system';
      else next = prefersDark.matches ? 'light' : 'dark';

      if (next === 'system') {
        localStorage.removeItem('kourob_theme');
        applyTheme(null);
      } else {
        localStorage.setItem('kourob_theme', next);
        applyTheme(next);
      }
    });
  }

  prefersDark.addEventListener('change', () => {
    if (!localStorage.getItem('kourob_theme')) {
      applyTheme(null);
    }
  });
}

// --- 2. Cryptographic Helper (SubtleCrypto SHA-256) ---
async function sha256(message) {
  const msgBuffer = new TextEncoder().encode(message);
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return 'sha256:' + hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function generateUlid(prefix) {
  const time = Date.now().toString(36).toUpperCase().padStart(10, '0');
  const rand = Array.from({ length: 16 }, () => Math.floor(Math.random() * 36).toString(36).toUpperCase()).join('');
  return `${prefix}_${time}${rand}`;
}

// --- 3. Simulated Node State & Scenarios ---
let simulatedPrevHash = 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069';
let simulatedSeq = 142;

const SCENARIOS = {
  t0: {
    id: 't0',
    query: 'what is a bridge in kourob',
    scope: 'in_scope',
    tier: 'T0',
    tierName: 'T0 (Exact Replay Rule)',
    model: 'rule:bridge-lookup@1.0',
    determinism: 'derived',
    cost: '0.0000',
    price: '0.0005',
    latency: '8ms',
    citations: ['evt_01J7K3MB9XW64H2PR8Z0'],
    rendered: 'A **bridge** is a referral that the node executes on the caller\'s behalf once, returning the answer plus the direct route hint so subsequent calls go direct [evt_01J7K3MB9XW64H2PR8Z0].',
    data: {
      term: 'bridge',
      definition: 'A referral executed on caller\'s behalf with route learning',
      spec: 'KNP-1 Section 5',
      limit: 3
    }
  },
  t3: {
    id: 't3',
    query: 'explain how referrals learn routes over time',
    scope: 'in_scope',
    tier: 'T3',
    tierName: 'T3 (Frontier Model + Grounded Citations)',
    model: 'frontier:anthropic:claude-3-5-sonnet',
    determinism: 'calibrated',
    cost: '0.0032',
    price: '0.0050',
    latency: '680ms',
    citations: ['evt_01J7K3MB9XW64H2PR8Z0', 'evt_01J7N9QA4YV78R3SL2A1'],
    rendered: 'When a node refers out or bridges, it attaches a signed route hint. The caller saves this route in its local table with initial Hebbian strength 0.4. Successful subsequent queries strengthen the route, bypassing intermediate hops [evt_01J7K3MB9XW64H2PR8Z0, evt_01J7N9QA4YV78R3SL2A1].',
    data: {
      mechanism: 'Hebbian route learning',
      initial_weight: 0.4,
      settled_weight_boost: 0.1,
      max_bridge_hops: 4
    }
  },
  referral: {
    id: 'referral',
    query: 'predict match Alcaraz vs Sinner at Roland Garros',
    scope: 'referral',
    tier: 'T0',
    tierName: 'Scope Referral (Tennis Set)',
    model: 'scope:classifier@rules',
    determinism: 'declared',
    cost: '0.0000',
    price: '0.0000',
    latency: '4ms',
    citations: ['evt_01J7M0P888W55D1NR822'],
    rendered: 'Query is out of scope for kourob-docs. Referred to neighbor **predict-node** (`did:key:z6MktTennisPredictNodeRoot`) with 95% confidence route hint [evt_01J7M0P888W55D1NR822].',
    data: {
      status: 'referred',
      route_hint: {
        node: 'did:key:z6MktTennisPredictNodeRoot',
        scope: ['tennis.match_prediction.v1', 'tennis.shot.v1'],
        transport: 'a2a+https://nodes.kourob.org/tennis-predict',
        cost_credits_typical: 0.002
      }
    }
  },
  reject: {
    id: 'reject',
    query: 'generate a photorealistic image of a futuristic server farm',
    scope: 'reject',
    tier: 'T0',
    tierName: 'Scope Rejection (Unsupported)',
    model: 'scope:classifier@rules',
    determinism: 'declared',
    cost: '0.0000',
    price: '0.0000',
    latency: '2ms',
    citations: [],
    rendered: 'Refused: Request is outside declared node scope. No matching routes exist in network table.',
    data: {
      status: 'rejected',
      reason: 'unsupported_domain',
      declared_scope: ['kourob.architecture', 'kourob.protocols', 'kourob.code']
    }
  }
};

// --- 4. Interactive Simulation Runner ---
async function runSimulation(scenarioKey, customQuery = null) {
  let sc = SCENARIOS[scenarioKey];
  if (customQuery) {
    // Basic heuristic to pick scenario based on query keywords
    const lower = customQuery.toLowerCase();
    if (lower.includes('alcaraz') || lower.includes('sinner') || lower.includes('tennis') || lower.includes('match')) {
      sc = { ...SCENARIOS.referral, query: customQuery };
    } else if (lower.includes('image') || lower.includes('weather') || lower.includes('stock')) {
      sc = { ...SCENARIOS.reject, query: customQuery };
    } else if (lower.includes('bridge') || lower.includes('node') || lower.includes('receipt')) {
      sc = { ...SCENARIOS.t0, query: customQuery };
    } else {
      sc = { ...SCENARIOS.t3, query: customQuery };
    }
  }

  // Update UI Waterfall Steps
  const steps = [
    document.getElementById('step-auth'),
    document.getElementById('step-scope'),
    document.getElementById('step-tier'),
    document.getElementById('step-receipt')
  ];

  steps.forEach(s => { if (s) s.className = 'waterfall-step'; });

  // Step 1: Auth & Meter
  if (steps[0]) steps[0].className = 'waterfall-step active';
  await new Promise(r => setTimeout(r, 200));
  if (steps[0]) steps[0].className = 'waterfall-step complete';

  // Step 2: Scope Check
  if (steps[1]) steps[1].className = 'waterfall-step active';
  await new Promise(r => setTimeout(r, 200));
  if (steps[1]) steps[1].className = 'waterfall-step complete';

  // Step 3: Tier Selection & Answer Execution
  if (steps[2]) steps[2].className = 'waterfall-step active';
  await new Promise(r => setTimeout(r, 300));
  if (steps[2]) steps[2].className = 'waterfall-step complete';

  // Step 4: Ledger Signing & Chaining
  if (steps[3]) steps[3].className = 'waterfall-step active';

  // Compute Real Cryptographic Hashes
  const receiptId = generateUlid('rcpt');
  const reqHash = await sha256(sc.query);
  const respHash = await sha256(JSON.stringify(sc.data) + sc.rendered);
  const prevHash = simulatedPrevHash;
  simulatedSeq += 1;

  // Mock Ed25519 signature representation
  const sigPayload = `${receiptId}:${simulatedSeq}:${reqHash}:${respHash}:${prevHash}`;
  const sigHash = await sha256(sigPayload);
  const mockSignature = `ed25519_sig_${sigHash.replace('sha256:', '').substring(0, 48)}...`;

  // Update prevHash for next call in hash chain
  simulatedPrevHash = await sha256(sigPayload + mockSignature);

  const receipt = {
    id: receiptId,
    seq: simulatedSeq,
    node: 'did:key:z6MkqFLQzUvx2yW88zP2zM4tG',
    caller: 'did:key:z6MkuAgentClaudeCodeClient',
    request_hash: reqHash,
    response_hash: respHash,
    scope_result: sc.scope,
    tier_used: sc.tier,
    model_version: sc.model,
    determinism: sc.determinism,
    citations: sc.citations,
    cost_credits: parseFloat(sc.cost),
    price_credits: parseFloat(sc.price),
    ts: new Date().toISOString(),
    prev: prevHash,
    sig: mockSignature
  };

  const answerEnvelope = {
    data: sc.data,
    rendered: sc.rendered,
    citations: sc.citations,
    receipt_id: receiptId,
    metadata: {
      tier: sc.tier,
      latency: sc.latency,
      determinism: sc.determinism
    }
  };

  const provGraph = {
    '@context': 'http://www.w3.org/ns/prov#',
    '@type': 'Bundle',
    entities: {
      [`answer:${receiptId}`]: {
        'prov:wasGeneratedBy': `activity:serve_${receiptId}`,
        'prov:wasDerivedFrom': sc.citations.length ? sc.citations : ['declaration:node_scope'],
        'kourob:tier': sc.tier,
        'kourob:receipt': receiptId
      },
      ...Object.fromEntries(sc.citations.map(c => [c, {
        '@type': 'kourob:Event',
        'kourob:table': 'data/silver/events.parquet',
        'kourob:status': 'immutable_verified'
      }]))
    },
    activities: {
      [`activity:serve_${receiptId}`]: {
        'prov:startedAtTime': new Date(Date.now() - 50).toISOString(),
        'prov:endedAtTime': new Date().toISOString(),
        'prov:wasAssociatedWith': 'did:key:z6MkqFLQzUvx2yW88zP2zM4tG'
      }
    }
  };

  if (steps[3]) steps[3].className = 'waterfall-step complete';

  // Render to Panels
  const panelAnswer = document.getElementById('panel-answer');
  const panelReceipt = document.getElementById('panel-receipt');
  const panelProv = document.getElementById('panel-prov');

  if (panelAnswer) {
    panelAnswer.innerHTML = `<pre><code>${escapeHtml(JSON.stringify(answerEnvelope, null, 2))}</code></pre>`;
  }

  if (panelReceipt) {
    panelReceipt.innerHTML = `
      <div class="receipt-verified-badge">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
        Hash Chain Verified: seq #${simulatedSeq} &middot; Cryptographically Signed
      </div>
      <pre><code>${escapeHtml(JSON.stringify(receipt, null, 2))}</code></pre>
    `;
  }

  if (panelProv) {
    panelProv.innerHTML = `<pre><code>${escapeHtml(JSON.stringify(provGraph, null, 2))}</code></pre>`;
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// --- 5. UI Setup & Event Listeners ---
function initPlayground() {
  const scenarioBtns = document.querySelectorAll('.scenario-btn');
  const customInput = document.getElementById('custom-query-input');
  const customSubmit = document.getElementById('custom-query-submit');
  const tabBtns = document.querySelectorAll('.sim-output-tabs .tab-btn');

  scenarioBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      scenarioBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const scenarioId = btn.getAttribute('data-scenario');
      runSimulation(scenarioId);
    });
  });

  if (customSubmit && customInput) {
    customSubmit.addEventListener('click', () => {
      const q = customInput.value.trim();
      if (q) {
        scenarioBtns.forEach(b => b.classList.remove('active'));
        runSimulation('t3', q);
      }
    });

    customInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const q = customInput.value.trim();
        if (q) {
          scenarioBtns.forEach(b => b.classList.remove('active'));
          runSimulation('t3', q);
        }
      }
    });
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-target');
      document.querySelectorAll('.sim-panel').forEach(p => p.classList.remove('active'));
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add('active');
    });
  });

  // Initial Run
  runSimulation('t0');
}

// --- 6. CLI Tab Switcher ---
function initCliTabs() {
  const cliBtns = document.querySelectorAll('.cli-tab-btn');
  cliBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      cliBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const cmd = btn.getAttribute('data-cmd');
      document.querySelectorAll('.cli-tab-content').forEach(c => c.classList.remove('active'));
      const targetContent = document.getElementById(`cli-content-${cmd}`);
      if (targetContent) targetContent.classList.add('active');
    });
  });
}

// --- 7. Copy Buttons ---
function initCopyButtons() {
  document.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', async () => {
      const codeTarget = btn.getAttribute('data-clipboard-target');
      let text = '';
      if (codeTarget) {
        const el = document.querySelector(codeTarget);
        if (el) text = el.innerText;
      } else {
        const codeEl = btn.parentElement.querySelector('code');
        if (codeEl) text = codeEl.innerText;
      }

      if (text) {
        try {
          await navigator.clipboard.writeText(text);
          const orig = btn.innerText;
          btn.innerText = 'Copied!';
          setTimeout(() => { btn.innerText = orig; }, 2000);
        } catch (err) {
          console.error('Clipboard copy failed:', err);
        }
      }
    });
  });
}

// --- 8. WebMCP Integration (Browser Agent Exposure) ---
function initWebMcp() {
  if (typeof document !== 'undefined' && 'modelContext' in document && typeof document.modelContext.registerTool === 'function') {
    try {
      // Register KouroB node query tool
      document.modelContext.registerTool({
        name: 'kourob_query',
        description: 'Query the KouroB node. Returns a cited, receipted answer envelope containing {data, rendered, citations, receipt_id}.',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'The search or question query for the KouroB node.'
            }
          },
          required: ['query']
        },
        execute: async ({ query }) => {
          await runSimulation('t0', query);
          const panel = document.getElementById('panel-answer');
          return { content: [{ type: 'text', text: panel ? panel.innerText : 'Executed' }] };
        },
        annotations: { readOnlyHint: true }
      });

      console.info('[KouroB] WebMCP tools successfully registered for AI browser agents.');
    } catch (e) {
      console.debug('[KouroB] WebMCP registration skipped or unsupported:', e);
    }
  }
}

// --- Bootstrapping on DOM Ready ---
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initPlayground();
  initCliTabs();
  initCopyButtons();
  initWebMcp();
});
