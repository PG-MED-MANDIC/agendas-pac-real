/* Gerar slide (PowerPoint) — módulo autônomo, portado do projeto painel-gerador-slide.
 * Tudo roda no navegador: prints via html-to-image e .pptx via pptxgenjs. Nada é enviado a servidor.
 * Como usar em outro dash: incluir este arquivo e chamar GeradorSlide.iniciar({ titulo: 'Nome do dash' }).
 * Blocos selecionáveis = elementos de SEL.blocos da aba ativa (padrão do csat: `.cbox` e `.cards-row`).
 * Outros dashs passam `seletores` (aba, abaBotao, blocos, indicadores, titulo) e, opcionalmente,
 * `pilulas`/`rotulos` ([nome, seletor]) para o rodapé de filtros. */
(function () {
  'use strict';

  var LIBS = [
    'https://cdn.jsdelivr.net/npm/html-to-image@1.11.11/dist/html-to-image.js',
    'https://cdn.jsdelivr.net/npm/pptxgenjs@4.0.1/dist/pptxgen.bundle.js'
  ];
  var SEL = {
    aba: '.tab-content.active',
    abaBotao: '.tabs-nav .tab-btn.active',
    blocos: '.cbox, .cards-row',
    indicadores: '.cards-row',   // blocos deste tipo viram "Indicadores"
    titulo: 'h3',
    fundo: '#F5F7FC'
  };
  /* Medidas em polegadas, widescreen 16:9. */
  var W = 13.333, H = 7.5, MARG = 0.4, TOPO = 0.4, BAIXO = 6.75, ESP = 0.3;
  var cfg = { titulo: 'Dashboard' };
  var ativo = false;
  var itens = [];              // {id, secao, titulo, dataUrl, largura, altura, filtros}
  var blocosVivos = {};        // id -> elemento atual
  var overlays = {};           // id -> {moldura, rotulo}
  var porSlide = 2;
  var capturando = {};
  var raiz, barra, camada, modal, timer;

  /* ---------- utilidades ---------- */
  function el(tag, css, html) {
    var e = document.createElement(tag);
    if (css) e.style.cssText = css;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function texto(n) { return (n && n.textContent || '').replace(/\s+/g, ' ').trim(); }
  function carregar(src) {
    return new Promise(function (ok, erro) {
      var s = document.createElement('script');
      s.src = src; s.onload = ok;
      s.onerror = function () { erro(new Error('Falha ao carregar ' + src)); };
      document.head.appendChild(s);
    });
  }
  var libsPromessa;
  function garantirLibs() {
    if (window.htmlToImage && window.PptxGenJS) return Promise.resolve();
    if (!libsPromessa) {
      libsPromessa = Promise.all(LIBS.map(carregar)).catch(function (e) { libsPromessa = null; throw e; });
    }
    return libsPromessa;
  }

  /* Filtros genéricos (dashs sem função própria): selects visíveis com valor + botões/pílulas ativos. */
  function filtrosGenericos() {
    var p = [];
    document.querySelectorAll('select').forEach(function (s) {
      if (!s.offsetParent || !s.value) return;
      var rot = s.id, l = s.previousElementSibling;
      if (!l || l.tagName !== 'LABEL') { var pai = s.closest('.fg, .f'); l = pai && pai.querySelector('label'); }
      if (l) rot = texto(l).replace(/:$/, '');
      p.push(rot + ': ' + s.options[s.selectedIndex].text);
    });
    (cfg.pilulas || []).forEach(function (par) {
      var t = []; document.querySelectorAll(par[1]).forEach(function (n) { if (n.offsetParent) t.push(texto(n)); });
      if (t.length) p.push(par[0] + ': ' + t.join(', '));
    });
    (cfg.rotulos || []).forEach(function (par) {
      var n = document.querySelector(par[1]);
      if (n && n.offsetParent && texto(n) && !/^(todos|todas)/i.test(texto(n))) p.push(par[0] + ': ' + texto(n));
    });
    return p.length ? p.join(' · ') : 'Sem filtros (todos)';
  }

  /* Filtros ativos agora (vão no rodapé de cada bloco, para o slide dizer o que mostra). */
  function filtrosAtuais() {
    if (cfg.filtros) return cfg.filtros();
    if (cfg.seletores) return filtrosGenericos();
    var p = [];
    function sel(id, nome) {
      var s = document.getElementById(id);
      if (s && s.value) p.push(nome + ': ' + s.options[s.selectedIndex].text);
    }
    sel('f-unidade', 'Unidade'); sel('f-ano', 'Ano');
    var mes = document.getElementById('ms-mes-btn');
    if (mes && texto(mes) && texto(mes) !== 'Todos') p.push('Mês: ' + texto(mes));
    sel('f-hab', 'Habilitação'); sel('f-diturma', 'DI&Turma');
    var it = []; document.querySelectorAll('.fg-itens .icheck input:checked').forEach(function (c) { it.push(c.value); });
    if (it.length) p.push('Itens: ' + it.join(', '));
    var sem = []; document.querySelectorAll('#semana-checkboxes input:checked').forEach(function (c) { sem.push(c.value || texto(c.parentNode)); });
    if (sem.length) p.push('Semana: ' + sem.join(', '));
    return p.length ? p.join(' · ') : 'Sem filtros (todos)';
  }

  /* ---------- blocos da aba atual ---------- */
  function listarBlocos() {
    var aba = document.querySelector(SEL.aba);
    if (!aba) return [];
    var secao = texto(document.querySelector(SEL.abaBotao)).replace(/^[^\wÀ-ú]+/, '') || 'Aba';
    var cont = {}, lista = [];
    aba.querySelectorAll(SEL.blocos).forEach(function (b) {
      if (!b.offsetParent || b.offsetWidth < 120 || b.offsetHeight < 40) return;
      var t = b.matches(SEL.indicadores) ? 'Indicadores' : texto(b.querySelector(SEL.titulo)) || 'Bloco';
      cont[t] = (cont[t] || 0) + 1;
      var id = secao + '::' + t + (cont[t] > 1 ? ' #' + cont[t] : '');
      lista.push({ id: id, secao: secao, titulo: t + (cont[t] > 1 ? ' (' + cont[t] + ')' : ''), elemento: b });
    });
    return lista;
  }

  function estaSelecionado(id) { return itens.some(function (i) { return i.id === id; }); }

  function capturar(b) {
    return garantirLibs().then(function () {
      var e = b.elemento;
      return window.htmlToImage.toPng(e, {
        pixelRatio: 2, backgroundColor: SEL.fundo,
        filter: function (n) { return !(n.dataset && 'semCaptura' in n.dataset); }
      }).then(function (dataUrl) {
        return { id: b.id, secao: b.secao, titulo: b.titulo, dataUrl: dataUrl,
                 largura: e.offsetWidth, altura: e.offsetHeight, filtros: filtrosAtuais() };
      });
    });
  }

  function alternar(b, marcado, rotulo) {
    if (!marcado) { itens = itens.filter(function (i) { return i.id !== b.id; }); atualizar(); return Promise.resolve(); }
    if (capturando[b.id]) return Promise.resolve();
    capturando[b.id] = true; atualizar();
    return capturar(b).then(function (item) {
      if (!estaSelecionado(b.id)) itens.push(item);
    }).catch(function (e) {
      console.error(e); aviso('Não foi possível tirar o print de "' + b.titulo + '".');
    }).then(function () { delete capturando[b.id]; atualizar(); });
  }

  /* ---------- camada de seleção (fora dos blocos: o dash recria o conteúdo ao filtrar) ---------- */
  function sincronizar() {
    if (!ativo) return;
    var blocos = listarBlocos(), vistos = {};
    blocosVivos = {};
    blocos.forEach(function (b) {
      vistos[b.id] = true; blocosVivos[b.id] = b;
      var o = overlays[b.id];
      if (!o) {
        o = overlays[b.id] = { moldura: el('div', 'position:absolute;pointer-events:none;border-radius:8px;box-sizing:border-box;'),
                               rotulo: el('label', 'position:absolute;display:flex;align-items:center;gap:6px;padding:4px 10px;border-radius:14px;font:600 12px system-ui,sans-serif;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.25);user-select:none;') };
        var cb = document.createElement('input'); cb.type = 'checkbox'; cb.style.cursor = 'pointer';
        var sp = document.createElement('span'); o.rotulo.appendChild(cb); o.rotulo.appendChild(sp);
        o.cb = cb; o.sp = sp;
        cb.addEventListener('change', function () { alternar(blocosVivos[b.id] || b, cb.checked, o); });
        camada.appendChild(o.moldura); camada.appendChild(o.rotulo);
      }
      var r = b.elemento.getBoundingClientRect(), sx = window.pageXOffset, sy = window.pageYOffset;
      var sel = estaSelecionado(b.id), cap = !!capturando[b.id];
      o.moldura.style.cssText += ';left:' + (r.left + sx) + 'px;top:' + (r.top + sy) + 'px;width:' + r.width + 'px;height:' + r.height +
        'px;border:' + (sel ? '3px solid #01559B;background:rgba(1,85,155,.06)' : '2px dashed #9aa5c4;background:transparent');
      o.rotulo.style.left = (r.right + sx - 150) + 'px'; o.rotulo.style.top = (r.top + sy + 6) + 'px';
      o.rotulo.style.background = sel ? '#01559B' : '#fff'; o.rotulo.style.color = sel ? '#fff' : '#1A2459';
      o.rotulo.style.border = '1px solid ' + (sel ? '#01559B' : '#9aa5c4');
      o.cb.checked = sel; o.cb.disabled = cap;
      o.sp.textContent = cap ? 'Capturando…' : 'Incluir no slide';
    });
    Object.keys(overlays).forEach(function (id) {
      if (!vistos[id]) { overlays[id].moldura.remove(); overlays[id].rotulo.remove(); delete overlays[id]; }
    });
  }

  /* ---------- barra flutuante ---------- */
  function btn(rot, fn, css) {
    var b = el('button', 'border:0;border-radius:6px;padding:7px 12px;font:600 12px system-ui,sans-serif;cursor:pointer;background:#fff;color:#1A2459;' + (css || ''), rot);
    b.addEventListener('click', fn); return b;
  }
  function montarBarra() {
    barra = el('div', 'position:fixed;right:18px;bottom:18px;z-index:9500;background:#1A2459;color:#fff;border-radius:10px;padding:10px 12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;box-shadow:0 4px 18px rgba(0,0,0,.35);font:12px system-ui,sans-serif;max-width:min(96vw,640px)');
    barra.setAttribute('data-sem-captura', '');
    document.body.appendChild(barra);
    atualizarBarra();
  }
  function atualizarBarra() {
    if (!barra) return;
    barra.innerHTML = '';
    if (!ativo) {
      barra.appendChild(btn('📊 Gerar slide', ligar, 'background:#F5C518;color:#1A2459;'));
      return;
    }
    barra.appendChild(el('span', 'font-weight:700', 'Modo slide · ' + itens.length + ' bloco(s) escolhido(s)'));
    barra.appendChild(btn('Incluir tudo da aba', incluirTudo));
    barra.appendChild(btn('Limpar escolhas', function () { itens = []; atualizar(); }));
    var ver = btn('Ver prévia / baixar', abrirPrevia, 'background:#F5C518;');
    if (!itens.length) { ver.disabled = true; ver.style.opacity = '.5'; ver.style.cursor = 'not-allowed'; }
    barra.appendChild(ver);
    barra.appendChild(btn('Sair', desligar, 'background:transparent;color:#fff;border:1px solid #fff;'));
  }
  function atualizar() { atualizarBarra(); sincronizar(); if (modal) desenharPrevia(); }
  function aviso(msg) {
    var a = el('div', 'position:fixed;left:50%;transform:translateX(-50%);bottom:80px;z-index:9700;background:#dc2626;color:#fff;padding:8px 14px;border-radius:6px;font:12px system-ui,sans-serif', msg);
    document.body.appendChild(a); setTimeout(function () { a.remove(); }, 4000);
  }
  function incluirTudo() {
    var pend = Object.keys(blocosVivos).map(function (id) { return blocosVivos[id]; }).filter(function (b) { return !estaSelecionado(b.id); });
    (function prox() { if (!pend.length) return; alternar(pend.shift(), true).then(prox); })();
  }

  function ligar() {
    ativo = true; camada.style.display = 'block'; atualizarBarra(); sincronizar();
    timer = setInterval(sincronizar, 400);
  }
  function desligar() {
    ativo = false; clearInterval(timer); camada.style.display = 'none'; atualizarBarra();
  }

  /* ---------- prévia ---------- */
  function paginar() {
    var p = [];
    for (var i = 0; i < itens.length; i += porSlide) p.push(itens.slice(i, i + porSlide));
    return p;
  }
  function mover(i, d) {
    var j = i + d;
    if (j < 0 || j >= itens.length) return;
    var t = itens[i]; itens[i] = itens[j]; itens[j] = t; desenharPrevia();
  }
  function abrirPrevia() {
    if (!itens.length) return;
    modal = el('div', 'position:fixed;inset:0;z-index:9800;background:rgba(15,20,50,.72);display:flex;align-items:center;justify-content:center;padding:16px');
    modal.setAttribute('data-sem-captura', '');
    document.body.appendChild(modal); desenharPrevia();
  }
  function fecharPrevia() { if (modal) { modal.remove(); modal = null; } }

  function desenharPrevia() {
    if (!modal) return;
    if (!itens.length) { fecharPrevia(); return; }
    modal.innerHTML = '';
    var caixa = el('div', 'background:#F5F7FC;border-radius:12px;width:min(1100px,100%);max-height:94vh;display:flex;flex-direction:column;font:13px system-ui,sans-serif;color:#1a1a2e');
    var topo = el('div', 'padding:14px 18px;border-bottom:1px solid #e5e7eb;display:flex;gap:12px;align-items:center;flex-wrap:wrap');
    topo.appendChild(el('strong', 'font-size:16px;color:#1A2459', 'Prévia do PowerPoint'));
    var sel = el('select', 'padding:5px 8px;border:1px solid #cbd0e0;border-radius:4px');
    [[1, '1 bloco por slide'], [2, '2 blocos por slide'], [4, '4 blocos por slide']].forEach(function (o) {
      var op = document.createElement('option'); op.value = o[0]; op.textContent = o[1]; if (o[0] === porSlide) op.selected = true; sel.appendChild(op);
    });
    sel.addEventListener('change', function () { porSlide = +sel.value; desenharPrevia(); });
    topo.appendChild(sel);
    topo.appendChild(el('span', 'color:#6b7280;flex:1', paginar().length + ' slide(s) · use ◀ ▶ para trocar a ordem'));
    var baixar = btn('⬇ Baixar PowerPoint', function () {
      baixar.disabled = true; baixar.textContent = 'Gerando…';
      gerarPptx().catch(function (e) { console.error(e); aviso('Erro ao gerar o PowerPoint.'); })
        .then(function () { if (baixar) { baixar.disabled = false; baixar.textContent = '⬇ Baixar PowerPoint'; } });
    }, 'background:#01559B;color:#fff;');
    topo.appendChild(baixar);
    topo.appendChild(btn('Fechar', fecharPrevia, 'border:1px solid #cbd0e0;'));
    caixa.appendChild(topo);

    var corpo = el('div', 'padding:16px 18px;overflow:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px');
    var pos = posicoes(porSlide), idx = 0;
    paginar().forEach(function (pag, n) {
      var wrap = el('div', '');
      wrap.appendChild(el('div', 'font-weight:700;color:#1A2459;margin-bottom:4px', 'Slide ' + (n + 1)));
      var pg = el('div', 'position:relative;width:100%;aspect-ratio:' + W + '/' + H + ';background:#fff;border:1px solid #cbd0e0;border-radius:4px;overflow:hidden');
      pag.forEach(function (it, k) {
        var r = pos[k], i = idx++;
        var bl = el('div', 'position:absolute;box-sizing:border-box;border:1px solid #e5e7eb;display:flex;flex-direction:column;background:#fff;overflow:hidden;' +
          'left:' + (r.x / W * 100) + '%;top:' + (r.y / H * 100) + '%;width:' + (r.w / W * 100) + '%;height:' + (r.h / H * 100) + '%');
        var cab = el('div', 'display:flex;align-items:center;gap:4px;padding:2px 4px;background:#eef1fa;font-size:10px;font-weight:700;color:#1A2459');
        cab.appendChild(el('span', 'flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis', legenda(it)));
        [['◀', -1], ['▶', 1]].forEach(function (a) {
          var b = btn(a[0], function () { mover(i, a[1]); }, 'padding:0 5px;font-size:10px;border:1px solid #cbd0e0;');
          cab.appendChild(b);
        });
        cab.appendChild(btn('✕', function () { itens = itens.filter(function (x) { return x.id !== it.id; }); atualizar(); }, 'padding:0 5px;font-size:10px;color:#dc2626;border:1px solid #cbd0e0;'));
        var im = el('img', 'flex:1;min-height:0;object-fit:contain;width:100%'); im.src = it.dataUrl;
        bl.appendChild(cab); bl.appendChild(im); pg.appendChild(bl);
      });
      wrap.appendChild(pg); corpo.appendChild(wrap);
    });
    caixa.appendChild(corpo);
    caixa.appendChild(el('div', 'padding:8px 18px;border-top:1px solid #e5e7eb;color:#6b7280;font-size:11px',
      '⚠ O print leva exatamente o que está na tela. Abas de comentários podem conter nome de aluno: confira antes de compartilhar o arquivo.'));
    modal.appendChild(caixa);
  }

  /* ---------- layout e PowerPoint ---------- */
  function posicoes(n) {
    var cols = n === 1 ? 1 : 2, lins = n === 4 ? 2 : 1;
    var w = (W - MARG * 2 - ESP * (cols - 1)) / cols, h = (BAIXO - TOPO - ESP * (lins - 1)) / lins, r = [];
    for (var l = 0; l < lins; l++) for (var c = 0; c < cols; c++) r.push({ x: MARG + c * (w + ESP), y: TOPO + l * (h + ESP), w: w, h: h });
    return r;
  }
  function legenda(it) { return it.secao === it.titulo ? it.titulo : it.secao + ' › ' + it.titulo; }

  function gerarPptx() {
    return garantirLibs().then(function () {
      var ppt = new window.PptxGenJS();
      ppt.layout = 'LAYOUT_WIDE';
      var pos = posicoes(porSlide), LEG = 0.35, FIL = 0.2;
      paginar().forEach(function (pag) {
        var s = ppt.addSlide();
        pag.forEach(function (it, k) {
          var a = pos[k];
          s.addText(legenda(it), { x: a.x, y: a.y, w: a.w, h: LEG, fontFace: 'Segoe UI', fontSize: 12, bold: true, color: '1A2459', valign: 'middle', fit: 'shrink' });
          var topo = a.y + LEG + 0.03, livre = a.h - LEG - FIL - 0.06;
          var esc = Math.min(a.w / it.largura, livre / it.altura), w = it.largura * esc, h = it.altura * esc;
          s.addImage({ data: it.dataUrl.replace(/^data:/, ''), x: a.x + (a.w - w) / 2, y: topo + (livre - h) / 2, w: w, h: h });
          s.addText(it.filtros, { x: a.x, y: a.y + a.h - FIL, w: a.w, h: FIL, fontFace: 'Segoe UI', fontSize: 8, color: '5E6486', valign: 'middle', fit: 'shrink' });
        });
        var d = new Date();
        s.addText(cfg.titulo + ' · gerado em ' + d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }),
          { x: MARG, y: H - 0.55, w: W - MARG * 2, h: 0.3, fontFace: 'Segoe UI', fontSize: 10, color: '5E6486' });
      });
      return ppt.writeFile({ fileName: cfg.titulo.replace(/[^\w\-]+/g, '_') + '.pptx' });
    });
  }

  /* ---------- início ---------- */
  function iniciar(opcoes) {
    for (var k in (opcoes || {})) cfg[k] = opcoes[k];
    if (cfg.seletores) for (var q in cfg.seletores) SEL[q] = cfg.seletores[q];
    camada = el('div', 'position:absolute;left:0;top:0;width:0;height:0;z-index:9000;display:none');
    camada.setAttribute('data-sem-captura', '');
    document.body.appendChild(camada);
    montarBarra();
    /* A troca de aba muda os blocos; a seleção já feita continua valendo (print guardado). */
    window.addEventListener('resize', sincronizar);
    garantirLibs().catch(function () { /* tenta de novo ao capturar */ });
  }

  window.GeradorSlide = { iniciar: iniciar, _estado: function () { return { itens: itens, ativo: ativo }; } };
})();
