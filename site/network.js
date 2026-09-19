/* ==========================================================================
   examples.html: the topology, the recorded runs, and the receipt verifier.

   Everything rendered here comes from network.json, which is written by
   examples/trooth-network/export_web.py from an actual run of the seven nodes.
   The only thing this file invents is layout.
   ========================================================================== */

(function () {
  'use strict';

  const B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  const enc = new TextEncoder();
  let DATA = null;

  function esc(t) {
    return String(t).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  // ------------------------------------------------------------------ topology

  const NODES = {
    'trooth-desk': {
      kind: 'desk',
      title: 'trooth-desk',
      blurb: 'The front of the network. Holds no events at all: its whole job is to know which node does, and to say so in a recorded, signed referral.',
      rows: [
        ['holds', '0 events'],
        ['routes', 'weather-desk &middot; usgs-node &middot; bls-node &middot; fred-node'],
        ['decides by', 'four declared exclusions, matched in order'],
        ['introduces', 'once per caller, then it refers']
      ]
    },
    'weather-desk': {
      kind: 'desk',
      title: 'weather-desk',
      blurb: 'A second routing node, one level down. It splits weather by kind - a station reading is not a model forecast - and refers accordingly. This is the hop that makes the network two deep.',
      rows: [
        ['holds', '0 events'],
        ['routes', 'nws-node (station) &middot; open-meteo-node (model)'],
        ['decides by', 'two declared exclusions'],
        ['introduces', 'once per caller']
      ]
    },
    'nws-node': {
      kind: 'holds',
      title: 'nws-node',
      blurb: 'Observations from the US National Weather Service station at KJFK: temperature, humidity, wind, conditions. Answers from a compiled rule at no model cost.',
      rows: [
        ['holds', '3 events - observation, scorecard, emblem'],
        ['entity', 'weather-station'],
        ['source', 'api.weather.gov &middot; public domain'],
        ['credit', 'Data provided by NOAA / National Weather Service']
      ]
    },
    'open-meteo-node': {
      kind: 'holds',
      title: 'open-meteo-node',
      blurb: 'Model weather for the same coordinates - a different kind of claim about the same place, which is exactly why it is a different node.',
      rows: [
        ['holds', '3 events - observation, scorecard, emblem'],
        ['entity', 'weather-grid'],
        ['source', 'api.open-meteo.com &middot; CC-BY-4.0'],
        ['credit', 'Weather data by Open-Meteo.com']
      ]
    },
    'usgs-node': {
      kind: 'holds',
      title: 'usgs-node',
      blurb: 'The USGS past-hour earthquake feed: largest quake, magnitude, count. One hop from the front - no intermediate routing node needed.',
      rows: [
        ['holds', '3 events - observation, scorecard, emblem'],
        ['entity', 'earthquake'],
        ['source', 'earthquake.usgs.gov &middot; public domain'],
        ['credit', 'Data courtesy of the U.S. Geological Survey']
      ]
    },
    'bls-node': {
      kind: 'holds',
      title: 'bls-node',
      blurb: 'The Consumer Price Index from the Bureau of Labor Statistics. Ask the front node about inflation and it lands here.',
      rows: [
        ['holds', '3 events - observation, scorecard, emblem'],
        ['entity', 'price-index'],
        ['source', 'api.bls.gov &middot; public domain'],
        ['credit', 'U.S. Bureau of Labor Statistics']
      ]
    },
    'fred-node': {
      kind: 'holds',
      title: 'fred-node',
      blurb: 'Economic series from the St. Louis Fed. It holds the scorecard and the benchmark emblem but no envelope yet - FRED needs an API key - so it is the honest case of a node that is listed and graded but not yet fed.',
      rows: [
        ['holds', '2 events - scorecard, emblem (no envelope yet)'],
        ['entity', 'economic-series'],
        ['source', 'fred.stlouisfed.org &middot; API key required'],
        ['credit', 'Federal Reserve Economic Data (FRED)']
      ]
    }
  };

  const ASKS = {
    weather: { edges: ['front-weather', 'weather-nws'], nodes: ['trooth-desk', 'weather-desk', 'nws-node'], focus: 'nws-node' },
    model: { edges: ['front-weather', 'weather-openmeteo'], nodes: ['trooth-desk', 'weather-desk', 'open-meteo-node'], focus: 'open-meteo-node' },
    quake: { edges: ['front-usgs'], nodes: ['trooth-desk', 'usgs-node'], focus: 'usgs-node' },
    cpi: { edges: ['front-bls'], nodes: ['trooth-desk', 'bls-node'], focus: 'bls-node' }
  };

  function initTopology() {
    const detail = document.getElementById('net-detail');
    const groups = Array.from(document.querySelectorAll('.node-g'));
    const edges = Array.from(document.querySelectorAll('.edge'));
    const askBtns = Array.from(document.querySelectorAll('#network .net-ask'));
    if (!detail || !groups.length) return;

    function render(id) {
      const n = NODES[id];
      if (!n) return;
      const kindClass = n.kind === 'desk' ? 'kind-desk' : 'kind-holds';
      const kindText = n.kind === 'desk' ? 'Routing node - holds nothing' : 'Source node - holds events';
      detail.innerHTML =
        '<h3>' + n.title + '</h3>' +
        '<span class="detail-kind ' + kindClass + '">' + kindText + '</span>' +
        '<p>' + n.blurb + '</p>' +
        '<ul class="detail-rows">' +
        n.rows.map(function (r) {
          return '<li><span class="k">' + r[0] + '</span><span>' + r[1] + '</span></li>';
        }).join('') +
        '</ul>';
      groups.forEach(function (g) {
        g.classList.toggle('selected', g.getAttribute('data-node') === id);
      });
    }

    function clearRoute() {
      groups.forEach(function (g) { g.classList.remove('lit', 'dim'); });
      edges.forEach(function (e) { e.classList.remove('lit', 'dim'); });
    }

    function showRoute(key) {
      clearRoute();
      const route = ASKS[key];
      if (!route) return;
      groups.forEach(function (g) {
        const on = route.nodes.indexOf(g.getAttribute('data-node')) !== -1;
        g.classList.toggle('lit', on);
        g.classList.toggle('dim', !on);
      });
      edges.forEach(function (e) {
        const on = route.edges.indexOf(e.getAttribute('data-edge')) !== -1;
        e.classList.toggle('lit', on);
        e.classList.toggle('dim', !on);
      });
      render(route.focus);
    }

    groups.forEach(function (g) {
      const id = g.getAttribute('data-node');
      g.addEventListener('click', function () { render(id); });
      g.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); render(id); }
      });
    });

    askBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        askBtns.forEach(function (b) { b.classList.remove('active'); });
        const key = btn.getAttribute('data-ask');
        if (key === 'reset') { clearRoute(); render('trooth-desk'); return; }
        btn.classList.add('active');
        showRoute(key);
      });
    });

    render('trooth-desk');
  }

  // --------------------------------------------------------------- verification

  // Bitcoin-alphabet base58: what did:key and the signatures are written in.
  function b58decode(text) {
    let n = 0n;
    for (const ch of text) {
      const i = B58.indexOf(ch);
      if (i < 0) throw new Error('not base58: ' + ch);
      n = n * 58n + BigInt(i);
    }
    const bytes = [];
    while (n > 0n) { bytes.unshift(Number(n & 255n)); n >>= 8n; }
    let pad = 0;
    while (pad < text.length && text[pad] === '1') pad++;
    const out = new Uint8Array(pad + bytes.length);
    out.set(bytes, pad);
    return out;
  }

  // did:key:z<base58(0xed01 || raw key)>. This is why no registry is needed to check a
  // signature: the public key is inside the name.
  function keyFromDid(did) {
    const decoded = b58decode(did.replace(/^did:key:z/, ''));
    if (decoded[0] !== 0xed || decoded[1] !== 0x01) throw new Error('did:key is not ed25519');
    return decoded.slice(2);
  }

  async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest))
      .map(function (b) { return b.toString(16).padStart(2, '0'); })
      .join('');
  }

  let ed25519 = null;
  function importKey(raw) {
    return crypto.subtle.importKey('raw', raw, { name: 'Ed25519' }, false, ['verify']);
  }
  async function ed25519Available() {
    if (ed25519 !== null) return ed25519;
    try {
      await importKey(keyFromDid(DATA.nodes[0].did));
      ed25519 = true;
    } catch (e) {
      ed25519 = false;
    }
    return ed25519;
  }

  // One node's chain: every signature against that node's own key, every prev against the
  // record before it, and the first record against the genesis anchor bound to its did.
  async function verifyLedger(name, ledger, tamperAt) {
    const canVerify = await ed25519Available();
    const key = canVerify ? await importKey(keyFromDid(ledger.did)) : null;
    let prev = ledger.genesis_prev;
    let sigOk = 0;
    let chainOk = 0;
    let broke = null;

    for (let i = 0; i < ledger.records.length; i++) {
      const record = ledger.records[i];
      let signed = record.signed;
      if (tamperAt && tamperAt.node === name && tamperAt.index === i) {
        // Flip one digit inside the bytes that were signed. Nothing else changes.
        signed = signed.replace(/[0-9](?=["*,])/, function (d) {
          return String((Number(d) + 1) % 10);
        });
      }
      const bytes = enc.encode(signed);
      const body = JSON.parse(signed);

      if (body.prev === prev) {
        chainOk++;
      } else if (!broke) {
        broke = record.id + ': prev does not match the record before it';
      }

      if (canVerify) {
        const ok = await crypto.subtle.verify('Ed25519', key, b58decode(record.sig), bytes);
        if (ok) sigOk++;
        else if (!broke) broke = record.id + ': signature does not verify';
      }
      prev = 'sha256:' + (await sha256Hex(bytes));
    }
    return {
      name: name,
      records: ledger.records.length,
      sigOk: sigOk,
      chainOk: chainOk,
      broke: broke,
      canVerify: canVerify
    };
  }

  async function verifyAll(tamperAt) {
    const outEl = document.getElementById('verify-out');
    const names = Object.keys(DATA.ledgers);
    outEl.innerHTML = '<div class="verify-note">Checking ' + names.length + ' chains...</div>';
    const results = [];
    for (const name of names) {
      results.push(await verifyLedger(name, DATA.ledgers[name], tamperAt));
    }

    const canVerify = results.length > 0 && results[0].canVerify;
    const records = results.reduce(function (n, r) { return n + r.records; }, 0);
    const intact = results.filter(function (r) { return !r.broke; }).length;
    const firstBreak = results.find(function (r) { return r.broke; });

    let html = results.map(function (r) {
      const ok = !r.broke;
      const detail = !ok
        ? 'BROKEN'
        : r.records === 0
          ? 'no traffic yet'
          : (r.canVerify ? r.sigOk + ' signed / ' + r.chainOk + ' chained' : r.chainOk + ' chained');
      return '<div class="verify-row"><span>' + esc(r.name) + '</span><span class="' +
        (ok ? 'verify-ok' : 'verify-bad') + '">' + detail + '</span></div>';
    }).join('');

    html += '<div class="verify-row"><span><b>' + records + ' records</b></span><span class="' +
      (intact === results.length ? 'verify-ok' : 'verify-bad') + '">' + intact + '/' +
      results.length + ' chains intact</span></div>';

    if (tamperAt) {
      html += '<div class="verify-note">One digit was flipped inside <code>' + esc(tamperAt.node) +
        '</code> record ' + tamperAt.index + ' before checking. The signature covers those exact ' +
        'bytes, so it fails - and every record after it is unverifiable too.</div>';
    }
    if (!canVerify) {
      html += '<div class="verify-note">This browser has no Ed25519 in WebCrypto, so only the ' +
        'SHA-256 hash chain was checked. Signatures verify in current Chrome, Safari and Firefox.</div>';
    }
    if (firstBreak) {
      html += '<div class="verify-note verify-bad">' + esc(firstBreak.broke) + '</div>';
    }
    outEl.innerHTML = html;
  }

  // --------------------------------------------------------------- recorded runs

  function receiptOf(id) {
    const names = Object.keys(DATA.ledgers);
    for (const name of names) {
      const found = DATA.ledgers[name].records.find(function (r) { return r.id === id; });
      if (found) return { name: name, record: found };
    }
    return null;
  }

  // `decided_by` is a machine id. Render it as the sentence it stands for.
  function why(hop) {
    const raw = hop.decided_by || '';
    if (raw.indexOf('bridge:') === 0) return 'bridged to the node that holds it';
    if (raw.indexOf('rule:excl') === 0) return 'matched a declared exclusion, referred';
    if (raw.indexOf('rule:route-match') === 0) return 'matched a learned route, referred';
    if (raw.indexOf('rule:') === 0) return 'rule bound: ' + raw.slice(5);
    return raw || '-';
  }

  function credits(n) {
    if (!n) return '0';
    return n < 0.001 ? n.toExponential(1) : n.toFixed(5);
  }

  function hopTable(step) {
    if (!step.hops || !step.hops.length) return '';
    const rows = step.hops.map(function (h) {
      const tried = (h.tiers_tried || []).length ? (h.tiers_tried || []).join(', ') : '-';
      return '<tr>' +
        '<td>' + esc(h.node) + '</td>' +
        '<td class="why">' + esc(why(h)) + '</td>' +
        '<td>' + esc(tried) + '</td>' +
        '<td>' + (h.latency_ms != null ? h.latency_ms + ' ms' : '-') + '</td>' +
        '<td>' + credits(h.price_credits) + '</td>' +
        '<td><span class="rcpt" data-receipt="' + esc(h.receipt) + '">' + esc(h.receipt.slice(0, 14)) + '...</span></td>' +
        '</tr>';
    }).join('');
    return '<div class="scroll-x"><table class="hop-table">' +
      '<thead><tr><th>node</th><th>decided by</th><th>tried</th><th>latency</th><th>price</th><th>record</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
  }

  function renderThread(key) {
    const stepsEl = document.getElementById('thread-steps');
    const picker = document.getElementById('thread-picker');
    const thread = DATA.threads.find(function (t) { return t.key === key; });
    if (!thread) return;
    Array.from(picker.children).forEach(function (b) {
      b.classList.toggle('active', b.dataset.thread === key);
    });

    const totals = thread.totals || {};
    const head =
      '<div class="step-card" style="border-color: var(--accent-color);">' +
      '<div class="step-head"><span class="step-node">' + esc(thread.question) + '</span>' +
      '<span class="pill pill-tier">' + esc(thread.caller) + '</span></div>' +
      '<p style="margin:0 0 0.6rem; color: var(--text-secondary); font-size:0.88rem;">' +
      esc(thread.note) + '</p>' +
      '<div class="step-totals">' + (totals.asks || 0) + ' request(s) &middot; ' +
      (totals.hops || 0) + ' hops &middot; ' + (totals.latency_ms || 0) + ' ms total &middot; ' +
      'price ' + credits(totals.price_credits) + ' credits</div></div>';

    const steps = thread.steps.map(function (step, i) {
      const kind = step.scope_result;
      const pillKind = kind === 'bridge' ? 'bridge' : (kind === 'referral' ? 'referral' : 'reject');
      const pill = '<span class="pill pill-' + pillKind + '">' + esc(kind) + '</span>';
      const tier = step.tier
        ? '<span class="pill pill-tier">' + esc(step.tier) + ' ' + esc(step.determinism || '') + '</span>'
        : '';
      const hints = (step.hints && step.hints.length)
        ? '<div class="step-totals">route handed back: ' +
          step.hints.map(function (h) { return esc(h.to); }).join(', ') + '</div>'
        : '';
      const cites = (step.citations && step.citations.length)
        ? '<div class="step-totals">cites ' + step.citations.map(esc).join(', ') + '</div>'
        : '';
      const shape = (step.hops && step.hops.length && step.hops[0].shape)
        ? '<div class="step-totals">class signature: <code>' + esc(step.hops[0].shape) + '</code></div>'
        : '';
      return '<div class="step-card">' +
        '<div class="step-head"><span class="step-node">' + (i + 1) + '. asked ' +
        esc(step.asked) + '</span>' + pill + tier + '</div>' +
        '<p class="step-answer">' + esc(step.rendered) + '</p>' +
        hopTable(step) + shape + hints + cites +
        '<div class="signed-dump" hidden></div></div>';
    }).join('');

    stepsEl.innerHTML = head + steps;

    stepsEl.querySelectorAll('.rcpt').forEach(function (el) {
      el.addEventListener('click', function () {
        const found = receiptOf(el.dataset.receipt);
        if (!found) return;
        const dump = el.closest('.step-card').querySelector('.signed-dump');
        const pretty = JSON.stringify(JSON.parse(found.record.signed), null, 1);
        dump.textContent = found.name + ' signed exactly these bytes:\n\n' + pretty +
          '\n\nsignature (base58)\n' + found.record.sig;
        dump.hidden = false;
      });
    });
  }

  function initThreads() {
    const picker = document.getElementById('thread-picker');
    const stepsEl = document.getElementById('thread-steps');
    const outEl = document.getElementById('verify-out');
    const runBtn = document.getElementById('verify-run');
    const tamperBtn = document.getElementById('verify-tamper');
    if (!picker || !stepsEl) return;

    fetch('network.json').then(function (r) { return r.json(); }).then(function (data) {
      DATA = data;
      picker.innerHTML = DATA.threads.map(function (t) {
        const again = t.key.indexOf('-again') > -1 ? ' (asked again)' : '';
        return '<button class="net-ask" data-thread="' + esc(t.key) + '">"' +
          esc(t.question) + '"' + again + '</button>';
      }).join('');
      picker.querySelectorAll('button').forEach(function (b) {
        b.addEventListener('click', function () { renderThread(b.dataset.thread); });
      });
      renderThread(DATA.threads[0].key);
      const total = Object.keys(DATA.ledgers).reduce(function (n, k) {
        return n + DATA.ledgers[k].records.length;
      }, 0);
      outEl.innerHTML = '<div class="verify-note">' + total + ' signed records across ' +
        Object.keys(DATA.ledgers).length + ' chains, waiting to be checked.</div>';
    }).catch(function () {
      stepsEl.innerHTML = '<div class="step-card">Could not load <code>network.json</code>.</div>';
    });

    if (runBtn) runBtn.addEventListener('click', function () { verifyAll(null); });
    if (tamperBtn) {
      tamperBtn.addEventListener('click', function () {
        const names = Object.keys(DATA.ledgers).filter(function (n) {
          return DATA.ledgers[n].records.length > 0;
        });
        const node = names[Math.floor(Math.random() * names.length)];
        const index = Math.floor(Math.random() * DATA.ledgers[node].records.length);
        verifyAll({ node: node, index: index });
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initTopology();
    initThreads();
  });
})();
