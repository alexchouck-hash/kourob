/* The MAUDE method note, rendered from one real node run and verified in the browser.
 *
 * Everything on the page comes out of site/maude.json, which examples/maude-method-node/
 * export_site.py wrote by building the node from source, asking it every question, and
 * dumping the ledger as the exact bytes each record was signed over. Nothing here is
 * written by hand, so a claim on the page cannot drift from the event it cites.
 */
(function () {
  'use strict';

  var B58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  var enc = new TextEncoder();
  var DATA = null;

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function short(id) {
    return String(id).length > 22 ? String(id).slice(0, 18) + '…' : String(id);
  }

  // ------------------------------------------------------------------- render

  // One claim: what the node answered, the event it cited, and what the hop cost.
  function claimHtml(answer, events) {
    var event = events[answer.citations[0]] || {};
    // The rendered answer ends with its own citation in brackets; the id is shown
    // separately below, so strip the duplicate rather than print it twice.
    var body = String(answer.rendered || '').replace(/\s*\[evt_[0-9A-Z]+\]\s*$/, '');
    return '' +
      '<article class="claim" id="' + esc(answer.topic) + '">' +
        '<h3 class="claim-topic">' +
          '<a href="#' + esc(answer.topic) + '">' + esc(answer.topic.replace(/-/g, ' ')) + '</a>' +
        '</h3>' +
        '<p class="claim-body">' + esc(body) + '</p>' +
        '<dl class="claim-meta">' +
          '<div><dt>asked</dt><dd><code>' + esc(answer.question) + '</code></dd></div>' +
          '<div><dt>tier</dt><dd><span class="tier-pill">' + esc(answer.tier) + '</span> ' +
            esc(answer.determinism) + '</dd></div>' +
          '<div><dt>bound by</dt><dd><code>' + esc(answer.decided_by || 'n/a') + '</code></dd></div>' +
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

  function render() {
    var head = document.getElementById('run-facts');
    head.innerHTML = '' +
      '<div><dt>node</dt><dd><code>' + esc(DATA.node.name) + '</code></dd></div>' +
      '<div><dt>did:key</dt><dd><code class="did" title="' + esc(DATA.node.did) + '">' +
        esc(DATA.node.did) + '</code></dd></div>' +
      '<div><dt>scope</dt><dd>' + esc(DATA.node.scope) + '</dd></div>' +
      '<div><dt>autonomy</dt><dd>' + esc(DATA.node.autonomy) + ' (every change is a proposal)</dd></div>' +
      '<div><dt>held</dt><dd>' + esc(DATA.counts.events) + ' events, one per heading</dd></div>' +
      '<div><dt>served</dt><dd>' + esc(DATA.counts.answers) + ' answers, ' +
        esc(DATA.counts.records) + ' signed receipts</dd></div>';

    var body = document.getElementById('sections');
    body.innerHTML = DATA.sections.map(function (section) {
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

  // did:key:z<base58(0xed01 || raw key)>. The public key is inside the name, which is
  // why checking a signature needs no registry and no server.
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

  async function verifyChain(tamperIndex) {
    var canVerify = true;
    var key = null;
    try {
      key = await importKey(keyFromDid(DATA.node.did));
    } catch (e) {
      canVerify = false;
    }

    var prev = DATA.node.genesis_prev;
    var sigOk = 0, chainOk = 0, broke = null;

    for (var i = 0; i < DATA.records.length; i++) {
      var record = DATA.records[i];
      var signed = record.signed;
      if (tamperIndex === i) {
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
    return { total: DATA.records.length, sigOk: sigOk, chainOk: chainOk, broke: broke, canVerify: canVerify };
  }

  async function runVerify(tamperIndex) {
    var out = document.getElementById('verify-out');
    out.innerHTML = '<div class="verify-note">Checking ' + DATA.records.length + ' records…</div>';
    var r = await verifyChain(tamperIndex);
    var intact = !r.broke;
    var html = '';
    html += '<div class="verify-row"><span>hash chain, each <code>prev</code> against the record before it</span>' +
      '<span class="' + (r.chainOk === r.total ? 'verify-ok' : 'verify-bad') + '">' +
      r.chainOk + '/' + r.total + '</span></div>';
    html += '<div class="verify-row"><span>ed25519 signatures against the node’s own <code>did:key</code></span>' +
      '<span class="' + (r.canVerify ? (r.sigOk === r.total ? 'verify-ok' : 'verify-bad') : 'verify-note') + '">' +
      (r.canVerify ? r.sigOk + '/' + r.total : 'unavailable') + '</span></div>';
    if (r.broke) {
      html += '<div class="verify-row verify-bad"><span>first break</span><span><code>' +
        esc(r.broke) + '</code></span></div>';
    }
    if (tamperIndex !== null && tamperIndex !== undefined) {
      html += '<div class="verify-note">One digit was flipped inside record ' + (tamperIndex + 1) +
        ' before checking. Its signature no longer verifies, and the record after it no longer ' +
        'matches the hash of what it follows, so the edit shows up twice and cannot be quietly ' +
        'patched in one place.</div>';
    } else if (intact) {
      html += '<div class="verify-note">Nothing was taken on trust. The public key came out of the ' +
        '<code>did:key</code>, and the bytes checked are the bytes shown.</div>';
    }
    if (!r.canVerify) {
      html += '<div class="verify-note">This browser has no Ed25519 in WebCrypto, so only the SHA-256 ' +
        'chain was checked. Signatures verify in current Chrome, Safari and Firefox.</div>';
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
        runVerify(Math.floor(DATA.records.length / 2));
      });
      return runVerify(null);
    })
    .catch(function (err) {
      var out = document.getElementById('verify-out');
      if (out) out.innerHTML = '<div class="verify-row verify-bad"><span>could not load the run</span><span><code>' +
        esc(err.message) + '</code></span></div>';
      var body = document.getElementById('sections');
      if (body) body.innerHTML = '<p class="claim-body">The export did not load. Rebuild it with ' +
        '<code>uv run python examples/maude-method-node/export_site.py --out site/maude.json</code>.</p>';
    });
})();
