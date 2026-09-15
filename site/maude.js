/* The MAUDE method note, assembled by a network of cells and verified in the browser.
 *
 * Everything on the page comes out of site/maude.json, which
 * examples/method-network/export_site.py wrote by building five cells from source, putting
 * every section question to a desk that holds nothing, following the routes the desk handed
 * back, and dumping each cell's ledger as the exact bytes it signed. Nothing here is written
 * by hand, so a claim on the page cannot drift from the event it cites or from the cell that
 * vouched for it.
 */
(function () {
  'use strict';

  var B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  var enc = new TextEncoder();
  var DATA = null;

  /* The 10xAnd offer terms. Everything here is the operator's to set, and every one of
   * them is null until they do. A null renders as a visible "not set" marker rather than
   * as a raw {{PLACEHOLDER}} string, because a mustache left showing on a live page is
   * the failure the Phase 2 audit called out by name (G4), and rather than an invented
   * number, which Hard Constraint 3 forbids outright. Set them here and nowhere else.
   */
  var OFFER = {
    doc: '10X-CS-001',
    rev: 'REV B',
    method: 'maudescope dedup v0.1',
    claims: 'counts and estimates only; no rate, no ranking, no causation',
    validation: 'design targets; no labelled set exists yet',
    offer: 'Post-market signal review, one product code',
    scope: null,      // {{PMS_SCOPE}}
    price: null,      // {{PRICE_BAND_PMS}}
    leadTime: null,   // {{LEAD_TIME_PMS}}
    slots: '3 founding clients',
    bookUrl: null     // {{CALENDLY_URL}}
  };

  // What each cell is for, in one line, for readers who will not read a scope summary.
  var CELL_BLURB = {
    'fda-facts': 'what the dataset structurally is',
    'maude-method': 'how distinct events are estimated',
    'eval-gates': 'whether the method works, and what has actually been measured',
    'claims-policy': 'what any output may and may not say',
    'method-desk': 'holds nothing; routes every question to whoever owns it'
  };

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function short(id) {
    return String(id).length > 22 ? String(id).slice(0, 18) + '…' : String(id);
  }

  // A value the operator has not supplied yet. Says so, in place, in their accent colour.
  function orUnset(value, what) {
    return value ? esc(value) : '<span class="unset" title="Set this in OFFER at the top of ' +
      'maude.js">' + esc(what) + ' not set</span>';
  }

  // ------------------------------------------------------------------- render

  // How the question reached its answer: bridged through the desk, or straight to the cell
  // the desk had already named. The second is what referral learning looks like.
  function routeHtml(answer) {
    var path = answer.path || [];
    if (answer.scope_result === 'bridge') {
      return '<span class="route route-bridge">bridged via method-desk</span> ' +
        '<span class="route-hops">' + esc(answer.hop_count) + ' hops</span>';
    }
    if (path.length > 1) {
      return '<span class="route route-direct">direct to ' + esc(path[path.length - 1]) +
        '</span> <span class="route-hops">route already known</span>';
    }
    return '<span class="route">' + esc(answer.scope_result) + '</span>';
  }

  function claimHtml(answer, events) {
    var event = events[answer.citations[0]] || {};
    // The rendered answer ends with its own citation in brackets; the id is shown
    // separately below, so strip the duplicate rather than print it twice.
    var body = String(answer.rendered || '').replace(/\s*\[evt_[0-9A-Z]+\]\s*$/, '');
    return '' +
      '<article class="claim" id="' + esc(answer.topic) + '">' +
        '<h3 class="claim-topic">' +
          '<a href="#' + esc(answer.topic) + '">' + esc(answer.topic.replace(/-/g, ' ')) + '</a>' +
          '<span class="held-by" title="the cell that vouched for this claim">' +
            esc(answer.answered_by) + '</span>' +
        '</h3>' +
        '<p class="claim-body">' + esc(body) + '</p>' +
        '<dl class="claim-meta">' +
          '<div><dt>asked</dt><dd><code>' + esc(answer.question) + '</code></dd></div>' +
          '<div><dt>route</dt><dd>' + routeHtml(answer) + '</dd></div>' +
          '<div><dt>tier</dt><dd><span class="tier-pill">' + esc(answer.tier) + '</span> ' +
            esc(answer.determinism) + '</dd></div>' +
          '<div><dt>cites</dt><dd><code title="' + esc(answer.citations[0]) + '">' +
            esc(short(answer.citations[0])) + '</code></dd></div>' +
          '<div><dt>source</dt><dd><code>' + esc(event.source || 'n/a') + '</code></dd></div>' +
          '<div><dt>receipt</dt><dd><code title="' + esc(answer.receipt) + '">' +
            esc(short(answer.receipt)) + '</code></dd></div>' +
          '<div><dt>price</dt><dd>' + esc(answer.price_credits) + ' credits</dd></div>' +
          '<div><dt>latency</dt><dd>' + esc(answer.latency_ms) + ' ms</dd></div>' +
        '</dl>' +
      '</article>';
  }

  function refusalHtml(refusal) {
    return '' +
      '<article class="claim claim-refused">' +
        '<h3 class="claim-topic"><span>refused</span>' +
          '<span class="held-by held-by-none">no cell holds this</span></h3>' +
        '<p class="claim-asked"><code>' + esc(refusal.question) + '</code></p>' +
        '<p class="claim-body">' + esc(refusal.rendered) + '</p>' +
        '<dl class="claim-meta">' +
          '<div><dt>why asked</dt><dd>' + esc(refusal.why_asked) + '</dd></div>' +
          '<div><dt>scope</dt><dd><span class="route route-reject">' +
            esc(refusal.scope_result) + '</span></dd></div>' +
          '<div><dt>citations</dt><dd>none, which is the point</dd></div>' +
          '<div><dt>receipt</dt><dd><code title="' + esc(refusal.receipt) + '">' +
            esc(short(refusal.receipt)) + '</code></dd></div>' +
        '</dl>' +
      '</article>';
  }

  function render() {
    var cells = DATA.cells;
    var names = Object.keys(cells);

    document.getElementById('cell-table').innerHTML = names.map(function (name) {
      var cell = cells[name];
      return '' +
        '<div class="cell-card' + (name === DATA.network.desk ? ' cell-desk' : '') + '">' +
          '<div class="cell-name">' + esc(name) + '</div>' +
          '<div class="cell-blurb">' + esc(CELL_BLURB[name] || cell.scope) + '</div>' +
          '<div class="cell-facts">' +
            '<span>' + esc(cell.events) + ' events</span>' +
            '<span>' + esc(cell.records.length) + ' receipts</span>' +
          '</div>' +
          '<code class="cell-did" title="' + esc(cell.did) + '">' + esc(cell.did) + '</code>' +
        '</div>';
    }).join('');

    document.getElementById('doc-control').innerHTML = '' +
      '<div class="doc-id"><span>' + esc(OFFER.doc) + '</span>' +
        '<span class="rev">' + esc(OFFER.rev) + '</span></div>' +
      '<dl>' +
        '<div><dt>Subject</dt><dd>Estimating distinct events from MAUDE report counts</dd></div>' +
        '<div><dt>Data</dt><dd>openFDA device/event, public</dd></div>' +
        '<div><dt>Method</dt><dd>' + esc(OFFER.method) + '</dd></div>' +
        '<div><dt>Validation</dt><dd>' + esc(OFFER.validation) + '</dd></div>' +
        '<div><dt>Claims</dt><dd>' + esc(OFFER.claims) + '</dd></div>' +
        '<div><dt>Assembled by</dt><dd>' + esc(DATA.network.cells) + ' cells, ' +
          esc(DATA.counts.answers) + ' answers, ' + esc(DATA.counts.refusals) +
          ' refusals, ' + esc(DATA.counts.records) + ' signed receipts</dd></div>' +
      '</dl>';

    var book = OFFER.bookUrl
      ? '<a href="' + esc(OFFER.bookUrl) + '" rel="noopener">book a call</a>'
      : '<span class="unset" title="Set OFFER.bookUrl at the top of maude.js">booking link not configured</span>';
    document.getElementById('pilot-block').innerHTML = '' +
      '<div class="doc-id"><span>10X-SVC-PMS</span><span class="rev">' + esc(OFFER.rev) + '</span></div>' +
      '<dl>' +
        '<div><dt>Offer</dt><dd>' + esc(OFFER.offer) + '</dd></div>' +
        '<div><dt>Scope</dt><dd>' + orUnset(OFFER.scope, 'scope') + '</dd></div>' +
        '<div><dt>Price</dt><dd>' + orUnset(OFFER.price, 'price band') + '</dd></div>' +
        '<div><dt>Lead time</dt><dd>' + orUnset(OFFER.leadTime, 'lead time') + '</dd></div>' +
        '<div><dt>Slots</dt><dd>' + esc(OFFER.slots) + '</dd></div>' +
        '<div><dt>Next step</dt><dd>' + book + '</dd></div>' +
      '</dl>';

    document.getElementById('sections').innerHTML = DATA.sections.map(function (section) {
      return '' +
        '<section class="method-section">' +
          '<header class="section-head">' +
            '<h2>' + esc(section.title) + '</h2>' +
            '<p>' + esc(section.blurb) + '</p>' +
          '</header>' +
          '<div class="claims">' +
            section.answers.map(function (a) { return claimHtml(a, DATA.events); }).join('') +
          '</div>' +
        '</section>';
    }).join('');

    document.getElementById('refusals').innerHTML = DATA.refusals.map(refusalHtml).join('');

    // Say plainly whether a model wrote anything. It did not, unless it did.
    document.getElementById('prose-note').innerHTML = DATA.network.prose.generated
      ? 'Connective prose on this page was generated at T3 by a model call through ' +
        '<code>runner/</code>, and every such claim is marked T3 in its own metadata.'
      : 'No model wrote any sentence on this page. Every claim is a T0 lookup against a stored ' +
        'event, which is why each one can be diffed against the source line it came from. ' +
        'Reason recorded by the export: <code>' + esc(DATA.network.prose.note) + '</code>';
  }

  // -------------------------------------------------------------- verification

  function b58decode(text) {
    var n = 0n;
    for (var i = 0; i < text.length; i++) {
      var k = B58.indexOf(text[i]);
      if (k < 0) throw new Error('not base58: ' + text[i]);
      n = n * 58n + BigInt(k);
    }
    var bytes = [];
    while (n > 0n) { bytes.unshift(Number(n & 255n)); n >>= 8n; }
    var pad = 0;
    while (pad < text.length && text[pad] === '1') pad++;
    var out = new Uint8Array(pad + bytes.length);
    out.set(bytes, pad);
    return out;
  }

  // did:key:z<base58(0xed01 || raw key)>. The public key is inside the name, which is why
  // checking a signature needs no registry and no server.
  function keyFromDid(did) {
    var decoded = b58decode(did.replace(/^did:key:z/, ''));
    if (decoded[0] !== 0xed || decoded[1] !== 0x01) throw new Error('did:key is not ed25519');
    return decoded.slice(2);
  }

  async function sha256Hex(bytes) {
    var digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest))
      .map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
  }

  function importKey(raw) {
    return crypto.subtle.importKey('raw', raw, { name: 'Ed25519' }, false, ['verify']);
  }

  // One cell's chain: every signature against that cell's own key, every prev against the
  // record before it, and the first record against the genesis anchor bound to its did.
  async function verifyCell(name, cell, tamper) {
    var canVerify = true;
    var key = null;
    try {
      key = await importKey(keyFromDid(cell.did));
    } catch (e) {
      canVerify = false;
    }

    var prev = cell.genesis_prev;
    var sigOk = 0, chainOk = 0, broke = null;

    for (var i = 0; i < cell.records.length; i++) {
      var record = cell.records[i];
      var signed = record.signed;
      if (tamper && tamper.cell === name && tamper.index === i) {
        // Flip one digit inside the bytes that were signed. Nothing else changes.
        signed = signed.replace(/[0-9](?=["*,])/, function (d) {
          return String((Number(d) + 1) % 10);
        });
      }
      var bytes = enc.encode(signed);
      var bodyJson = JSON.parse(signed);

      if (bodyJson.prev === prev) chainOk++;
      else if (!broke) broke = record.id + ': prev does not match the record before it';

      if (canVerify) {
        var ok = await crypto.subtle.verify('Ed25519', key, b58decode(record.sig), bytes);
        if (ok) sigOk++;
        else if (!broke) broke = record.id + ': signature does not verify';
      }
      prev = 'sha256:' + (await sha256Hex(bytes));
    }
    return {
      name: name, total: cell.records.length, sigOk: sigOk,
      chainOk: chainOk, broke: broke, canVerify: canVerify
    };
  }

  async function runVerify(tamper) {
    var out = document.getElementById('verify-out');
    var names = Object.keys(DATA.cells);
    out.innerHTML = '<div class="verify-note">Checking ' + names.length + ' chains…</div>';

    var results = [];
    for (var i = 0; i < names.length; i++) {
      results.push(await verifyCell(names[i], DATA.cells[names[i]], tamper));
    }

    var records = 0, intact = 0;
    var canVerify = results.length > 0 && results[0].canVerify;
    var html = results.map(function (r) {
      records += r.total;
      if (!r.broke) intact++;
      var detail = r.canVerify
        ? r.sigOk + '/' + r.total + ' signed, ' + r.chainOk + '/' + r.total + ' chained'
        : r.chainOk + '/' + r.total + ' chained';
      return '<div class="verify-row"><span><code>' + esc(r.name) + '</code></span><span class="' +
        (r.broke ? 'verify-bad' : 'verify-ok') + '">' + esc(detail) + '</span></div>';
    }).join('');

    html += '<div class="verify-row verify-total"><span><b>' + records +
      ' records across ' + results.length + ' cells</b></span><span class="' +
      (intact === results.length ? 'verify-ok' : 'verify-bad') + '">' + intact + '/' +
      results.length + ' chains intact</span></div>';

    var firstBreak = results.filter(function (r) { return r.broke; })[0];
    if (tamper) {
      html += '<div class="verify-note">One digit was flipped inside record ' + (tamper.index + 1) +
        ' of <code>' + esc(tamper.cell) + '</code> before checking. Its signature no longer ' +
        'verifies, and the record after it no longer matches the hash of what it follows, so ' +
        'the edit shows up twice and cannot be quietly patched in one place. The other cells ' +
        'are untouched and still verify, because each cell signs its own chain.</div>';
    } else if (intact === results.length) {
      html += '<div class="verify-note">Nothing was taken on trust. Each public key came out of ' +
        'its own <code>did:key</code>, and the bytes checked are the bytes shown.</div>';
    }
    if (firstBreak && firstBreak.broke) {
      html += '<div class="verify-row"><span>first break</span><span class="verify-bad"><code>' +
        esc(firstBreak.broke) + '</code></span></div>';
    }
    if (!canVerify) {
      html += '<div class="verify-note">This browser has no Ed25519 in WebCrypto, so only the ' +
        'SHA-256 chains were checked. Signatures verify in current Chrome, Safari and Firefox.</div>';
    }
    out.innerHTML = html;
  }

  // -------------------------------------------------------------------- boot

  fetch('maude.json')
    .then(function (r) {
      if (!r.ok) throw new Error('maude.json: HTTP ' + r.status);
      return r.json();
    })
    .then(function (data) {
      DATA = data;
      render();
      document.getElementById('verify-run').addEventListener('click', function () { runVerify(null); });
      document.getElementById('verify-tamper').addEventListener('click', function () {
        var name = Object.keys(DATA.cells).filter(function (n) {
          return DATA.cells[n].records.length > 1;
        })[0];
        runVerify({ cell: name, index: Math.floor(DATA.cells[name].records.length / 2) });
      });
      return runVerify(null);
    })
    .catch(function (err) {
      var out = document.getElementById('verify-out');
      if (out) out.innerHTML = '<div class="verify-row"><span>could not load the run</span>' +
        '<span class="verify-bad"><code>' + esc(err.message) + '</code></span></div>';
      var body = document.getElementById('sections');
      if (body) body.innerHTML = '<p class="claim-body">The export did not load. Rebuild it with ' +
        '<code>uv run python examples/method-network/export_site.py --out site/maude.json</code>.</p>';
    });
})();
