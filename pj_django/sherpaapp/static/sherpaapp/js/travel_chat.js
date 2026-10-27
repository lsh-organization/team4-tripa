/* TRIPA - AI 대화로 여행 만들기
 *
 * 화면 3칸: 대화 / 일정 초안 / 지도
 * - 서버(/travel_chat/)가 AI 답변과 '검증된 일정 초안'을 돌려준다.
 * - AI가 보낸 글자는 전부 textContent 로만 넣는다. (innerHTML 사용 안 함)
 */
(function () {
  'use strict';

  var app = document.getElementById('tcApp');
  if (!app) return;

  var tokenInput = app.querySelector('input[name="csrfmiddlewaretoken"]');
  var cfg = {
    chatUrl: app.dataset.chatUrl,
    applyUrl: app.dataset.applyUrl,
    addUrl: app.dataset.addUrl,
    previewUrl: app.dataset.previewUrl,
    loginUrl: app.dataset.loginUrl,
    sprite: app.dataset.sprite,
    csrf: tokenInput ? tokenInput.value : '',
    prefill: (app.dataset.prefill || '').trim(),
    budget: app.dataset.budget || ''
  };

  var STORE_KEY = 'tripa_chat_v1';
  var MAX_SEND = 14;
  var MAX_PINS = 12;
  var WEEK = ['일', '월', '화', '수', '목', '금', '토'];
  var TRANSPORT = { car: '자동차', walk: '도보', public_transport: '대중교통', bike: '자전거' };
  var BUDGET = { value: '가성비', premium: '비싸도 괜찮음' };
  var WELCOME = '안녕하세요! 어디로, 언제쯤 떠나고 싶으세요? 편하게 말씀해 주세요. 예를 들면 "제주도 2박 3일, 맛집 위주로 가고 싶어요" 처럼요.';
  var EXAMPLES = [
    '제주 2박 3일 맛집 여행',
    '부산 당일치기',
    '강릉 1박 2일 가성비로',
    '서울 3박 4일 커플 여행'
  ];

  var el = {
    list: document.getElementById('tcMessages'),
    form: document.getElementById('tcForm'),
    input: document.getElementById('tcInput'),
    send: document.getElementById('tcSend'),
    examples: document.getElementById('tcExamples'),
    reset: document.getElementById('tcReset'),
    apply: document.getElementById('tcApply'),
    edit: document.getElementById('tcEdit'),
    progress: document.getElementById('tcProgressBar'),
    progressText: document.getElementById('tcProgressText'),
    missing: document.getElementById('tcMissing'),
    notes: document.getElementById('tcNotes'),
    title: document.getElementById('tcTitle'),
    mapBox: document.getElementById('tcMap'),
    mapHint: document.getElementById('tcMapHint'),
    planTabs: document.getElementById('tcTabs'),
    planBody: document.getElementById('tcTimeline'),
    planState: document.getElementById('tcPlanState'),
    planRefresh: document.getElementById('tcPlanRefresh')
  };

  var state = {
    messages: [],       // {role, content, local?}
    draft: emptyDraft(),
    missing: ['여행 지역', '출발일', '종료일', '여행 컨셉'],
    ready: false,
    notes: [],
    busy: false,
    plan: null,         // {sig, rkey, days, transport}  서버가 만들어 준 일정 미리보기
    removed: [],        // 미리보기에서 지운 장소 [{day, name}]
    order: {},          // 미리보기에서 사용자가 바꾼 순서 {일차: [장소 이름, ...]}
    planBusy: false,
    planError: '',
    dayTab: 0
  };
  var planTimer = null;
  var removeTimer = null;

  /* ---------- 보관 (새로고침해도 대화 유지) ---------- */

  function load() {
    try {
      var raw = sessionStorage.getItem(STORE_KEY);
      if (!raw) return false;
      var saved = JSON.parse(raw);
      if (!saved || !Array.isArray(saved.messages) || !saved.draft) return false;
      state.messages = saved.messages.filter(isMessage);
      state.draft = Object.assign(emptyDraft(), saved.draft);
      state.missing = Array.isArray(saved.missing) ? saved.missing : state.missing;
      state.ready = !!saved.ready;
      state.plan = saved.plan && Array.isArray(saved.plan.days) ? saved.plan : null;
      state.removed = Array.isArray(saved.removed) ? saved.removed.filter(isRemoved) : [];
      state.order = cleanOrder(saved.order);
      return state.messages.length > 0;
    } catch (e) {
      return false;
    }
  }

  function save() {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({
        messages: state.messages.filter(function (m) { return !m.error; }).slice(-40),
        draft: state.draft,
        missing: state.missing,
        ready: state.ready,
        plan: state.plan,
        removed: state.removed,
        order: state.order
      }));
    } catch (e) { /* 저장이 안 돼도 동작에는 문제 없음 */ }
  }

  function clearStore() {
    try { sessionStorage.removeItem(STORE_KEY); } catch (e) { /* 무시 */ }
  }

  function cleanOrder(raw) {
    var out = {};
    if (!raw || typeof raw !== 'object') return out;
    Object.keys(raw).forEach(function (k) {
      if (!/^\d{1,2}$/.test(k) || !Array.isArray(raw[k])) return;
      var names = raw[k].filter(function (n) { return typeof n === 'string' && n; });
      if (names.length) out[k] = names;
    });
    return out;
  }

  function orderList() {
    return Object.keys(state.order).sort(function (a, b) { return a - b; }).map(function (k) {
      return { day: parseInt(k, 10), names: state.order[k] };
    });
  }

  function isRemoved(r) {
    return r && typeof r.day === 'number' && typeof r.name === 'string';
  }

  function isMessage(m) {
    return m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string';
  }

  function emptyDraft() {
    return {
      place: null, title: null, start: null, end: null, people: null,
      budget_style: null, budget_total: null, transport: null, categories: [],
      start_time: null, start_place: null, stays: [], center: null, pins: []
    };
  }

  /* ---------- 작은 도우미 ---------- */

  function make(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function icon(name) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'tp-icon');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    var use = document.createElementNS(ns, 'use');
    use.setAttribute('href', cfg.sprite + '#i-' + name);
    svg.appendChild(use);
    return svg;
  }

  function parseDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
    return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
  }

  function shortDate(iso) {
    var d = parseDate(iso);
    if (!d) return '';
    return (d.getMonth() + 1) + '/' + d.getDate() + '(' + WEEK[d.getDay()] + ')';
  }

  function dateText(draft) {
    if (!draft.start && !draft.end) return '';
    if (draft.start && !draft.end) return shortDate(draft.start) + ' 출발 · 종료일 미정';
    if (!draft.start && draft.end) return '출발일 미정 · ' + shortDate(draft.end) + ' 종료';
    var a = parseDate(draft.start), b = parseDate(draft.end);
    var nights = Math.round((b - a) / 86400000);
    var span = nights === 0 ? '당일치기' : nights + '박 ' + (nights + 1) + '일';
    return shortDate(draft.start) + ' ~ ' + shortDate(draft.end) + ' · ' + span;
  }

  function won(n) {
    return Number(n).toLocaleString('ko-KR') + '원';
  }

  /* ---------- 대화 화면 ---------- */

  function renderMessages() {
    el.list.textContent = '';

    state.messages.forEach(function (m) {
      el.list.appendChild(bubble(m.role, m.content, m.error, m.rec));
    });

    if (state.busy) {
      var typing = make('div', 'tc-msg tc-msg--bot');
      var dots = make('div', 'tc-bubble tc-typing');
      dots.setAttribute('aria-label', 'AI가 답변을 쓰는 중');
      for (var i = 0; i < 3; i++) dots.appendChild(make('span'));
      typing.appendChild(dots);
      el.list.appendChild(typing);
    }

    el.list.scrollTop = el.list.scrollHeight;
    el.examples.hidden = state.messages.length > 1 || state.busy;
  }

  function bubble(role, text, isError, rec) {
    var row = make('div', 'tc-msg ' + (role === 'user' ? 'tc-msg--me' : 'tc-msg--bot'));
    if (role !== 'user') {
      var avatar = make('span', 'tc-avatar');
      avatar.appendChild(icon('mountain'));
      row.appendChild(avatar);
    }
    var bubbleEl = make('div', 'tc-bubble' + (isError ? ' tc-bubble--error' : ''), text);

    if (rec && rec.items && rec.items.length) {
      row.className += ' tc-msg--rich';
      var col = make('div', 'tc-col');
      col.appendChild(bubbleEl);
      col.appendChild(renderRec(rec));
      row.appendChild(col);
    } else {
      row.appendChild(bubbleEl);
    }
    return row;
  }

  /* ---------- 장소 추천 카드 ---------- */

  var KIND_ICON = { '카페': 'cup', '음식': 'utensils', '숙박': 'bed', '쇼핑': 'bag', '관광': 'landmark' };

  function tripDays() {
    var a = parseDate(state.draft.start), b = parseDate(state.draft.end);
    if (!a || !b) return 0;
    return Math.round((b - a) / 86400000) + 1;
  }

  function hasPin(item, day) {
    return (state.draft.pins || []).some(function (p) { return p.day === day && p.name === item.name; });
  }

  function isLodging(item) { return item.kind === '숙박'; }

  function stayOn(day) {
    var iso = dayToIso(state.draft.start, day);
    return (state.draft.stays || []).filter(function (s) { return s.date === iso; })[0] || null;
  }

  function hasStay(item, day) {
    var s = stayOn(day);
    return !!s && (s.name === item.name || s.query === item.name);
  }

  function renderRec(rec) {
    var box = make('div', 'tc-rec');

    var cond = make('p', 'tc-rec__cond');
    cond.appendChild(make('span', null, '조건'));
    var parts = [];
    if (rec.anchor) parts.push(rec.anchor + ' 기준');
    if (rec.day) parts.push(rec.day + '일차');
    if (rec.time) parts.push(rec.time);
    cond.appendChild(make('span', 'tc-chip', parts.join(' · ') || rec.title));
    box.appendChild(cond);

    rec.items.forEach(function (item) {
      var card = make('div', 'tc-card');

      var tile = make('div', 'tc-card__icon');
      tile.appendChild(icon(KIND_ICON[item.kind] || 'pin'));
      card.appendChild(tile);

      var body = make('div', 'tc-card__body');
      var head = make('div', 'tc-card__head');
      head.appendChild(make('strong', null, item.name));
      head.appendChild(make('span', 'tc-tag', item.kind || '장소'));
      body.appendChild(head);

      var meta = make('p', 'tc-card__meta');
      meta.appendChild(icon('pin'));
      var metaText = [];
      if (item.distance) metaText.push((rec.anchor || '기준') + '에서 ' + item.distance);
      if (item.addr) metaText.push(item.addr);
      meta.appendChild(document.createTextNode(' ' + metaText.join(' · ')));
      body.appendChild(meta);

      var sub = make('p', 'tc-card__sub');
      if (item.phone) sub.appendChild(document.createTextNode(item.phone));
      if (item.url && /^https?:\/\/(place\.)?map\.kakao\.com\//.test(item.url)) {
        var link = make('a', 'tc-link', '카카오맵에서 보기');
        link.href = item.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        if (item.phone) sub.appendChild(document.createTextNode(' · '));
        sub.appendChild(link);
      }
      if (sub.childNodes.length) body.appendChild(sub);

      var actions = make('div', 'tc-card__actions');
      var n = tripDays();
      var days = [];
      if (rec.day && (!n || rec.day <= n)) days = [rec.day];
      else for (var d = 1; d <= Math.min(n, 7); d++) days.push(d);

      // 숙소는 '잠자는 밤'마다 하나. 마지막 날은 집으로 돌아가니 숙소가 필요 없다.
      var lodging = isLodging(item);
      if (lodging && n) {
        days = days.filter(function (d) { return d < n; });
        if (!days.length && n > 1) for (var nd = 1; nd < n && nd <= 7; nd++) days.push(nd);
      }

      if (!days.length) {
        var wait = make('button', 'tc-addbtn', lodging && n === 1 ? '당일치기라 숙소가 필요 없어요' : '날짜를 정하면 넣을 수 있어요');
        wait.type = 'button';
        wait.disabled = true;
        actions.appendChild(wait);
      }
      days.forEach(function (day) {
        var done = lodging ? hasStay(item, day) : hasPin(item, day);
        var b = make('button', 'tc-addbtn' + (done ? ' is-done' : ''));
        b.type = 'button';
        b.appendChild(icon(done ? 'check' : (lodging ? 'bed' : 'calendar')));
        b.appendChild(document.createTextNode(lodging
          ? ' ' + day + '일차 숙소로 ' + (done ? '담음' : '넣기')
          : ' ' + day + '일차에 ' + (done ? '담음' : '넣기')));
        b.disabled = done;
        b.addEventListener('click', function () {
          if (lodging) addStay(item, day); else addPin(item, day, rec.time);
        });
        actions.appendChild(b);
      });
      body.appendChild(actions);

      card.appendChild(body);
      box.appendChild(card);
    });

    return box;
  }

  function addPin(item, day, time) {
    if (state.busy || hasPin(item, day)) return;
    if ((state.draft.pins || []).length >= MAX_PINS) {
      state.notes = ['담을 수 있는 장소는 최대 ' + MAX_PINS + '곳이에요.'];
      renderDraft();
      return;
    }
    state.draft.pins = (state.draft.pins || []).concat([{
      day: day, name: item.name, addr: item.addr, kind: item.kind, lat: item.lat, lon: item.lon,
      phone: item.phone, url: item.url, time: time || null
    }]);
    state.notes = [];
    save();
    renderMessages();
    renderDraft(['추가한 장소']);
    maybePlan();
  }

  function addStay(item, day) {
    var n = tripDays();
    if (state.busy || !n || day >= n || hasStay(item, day)) return;
    var iso = dayToIso(state.draft.start, day);
    var stays = (state.draft.stays || []).filter(function (s) { return s.date !== iso; });
    stays.push({
      date: iso, query: item.name, name: item.name, addr: item.addr, lat: item.lat, lon: item.lon,
      arrival_time: null, departure_time: null
    });
    stays.sort(function (a, b) { return a.date < b.date ? -1 : 1; });
    state.draft.stays = stays;
    state.notes = [];
    save();
    renderMessages();
    renderDraft(['숙소']);
    maybePlan();
  }

  function removeStay(index) {
    if (state.busy) return;
    state.draft.stays = (state.draft.stays || []).filter(function (s, i) { return i !== index; });
    save();
    renderMessages();
    renderDraft();
    maybePlan();
  }

  function removePin(index) {
    if (state.busy) return;
    state.draft.pins = (state.draft.pins || []).filter(function (p, i) { return i !== index; });
    save();
    renderMessages();
    renderDraft();
    maybePlan();
  }

  function addBot(text, isError) {
    state.messages.push({ role: 'assistant', content: text, error: !!isError, local: !!isError });
  }

  /* ---------- 일정 초안 화면 ---------- */

  function setRow(key, valueNode, filled, changed) {
    var row = app.querySelector('[data-row="' + key + '"]');
    if (!row) return;
    var box = row.querySelector('.tc-val');
    box.textContent = '';
    if (filled) {
      box.appendChild(valueNode);
    } else {
      box.appendChild(make('span', 'tc-empty', '아직 정해지지 않았어요'));
    }
    row.classList.toggle('is-empty', !filled);
    row.classList.remove('is-new');
    if (changed) {
      void row.offsetWidth;
      row.classList.add('is-new');
    }
  }

  function renderDraft(changed) {
    var d = state.draft;
    changed = changed || [];

    el.title.textContent = d.title || '새 여행';

    setRow('place', document.createTextNode(d.place || ''), !!d.place, changed.indexOf('지역') > -1);
    setRow('date', document.createTextNode(dateText(d)), !!(d.start || d.end), changed.indexOf('날짜') > -1);

    var people = d.people ? d.people + '명' : '';
    setRow('people', document.createTextNode(people), !!d.people, changed.indexOf('인원') > -1);

    var concept = make('span', 'tc-chips');
    (d.categories || []).forEach(function (c) { concept.appendChild(make('span', 'tc-chip', c)); });
    setRow('concept', concept, (d.categories || []).length > 0, changed.indexOf('컨셉') > -1);

    setRow('transport', document.createTextNode(TRANSPORT[d.transport] || ''), !!TRANSPORT[d.transport], changed.indexOf('이동수단') > -1);

    var budgetParts = [];
    if (BUDGET[d.budget_style]) budgetParts.push(BUDGET[d.budget_style]);
    if (d.budget_total) budgetParts.push('총 ' + won(d.budget_total));
    setRow('budget', document.createTextNode(budgetParts.join(' · ')), budgetParts.length > 0, changed.indexOf('예산') > -1);

    var sp = d.start_place;
    var startNode = make('span');
    if (sp) {
      startNode.appendChild(document.createTextNode(sp.name || sp.query));
      if (d.start_time) startNode.appendChild(make('span', 'tc-sub', ' · ' + d.start_time + ' 출발'));
      if (sp.lat == null) startNode.appendChild(make('span', 'tc-warn', ' (위치 못 찾음)'));
    }
    setRow('start', startNode, !!sp, changed.indexOf('출발지') > -1);

    var stays = make('span', 'tc-stays');
    (d.stays || []).forEach(function (s, i) {
      var line = make('span', 'tc-stay');
      line.appendChild(make('span', 'tc-stay__date', shortDate(s.date)));
      line.appendChild(document.createTextNode(s.name || s.query));
      if (s.arrival_time) line.appendChild(make('span', 'tc-sub', ' · ' + s.arrival_time + ' 도착'));
      if (s.lat == null) line.appendChild(make('span', 'tc-warn', ' (위치 못 찾음)'));
      var sx = make('button', 'tc-x', '×');
      sx.type = 'button';
      sx.setAttribute('aria-label', (s.name || s.query) + ' 빼기');
      sx.addEventListener('click', function () { removeStay(i); });
      line.appendChild(sx);
      stays.appendChild(line);
    });

    // 숙소는 '잠자는 밤'마다 하나만 필요하다. (1박 2일이면 첫날 밤 하나, 마지막 날은 없음)
    var nTrip = tripDays();
    var stayFilled = (d.stays || []).length > 0;
    if (nTrip === 1) {
      stays.appendChild(make('span', 'tc-sub', '당일치기라 숙소가 필요 없어요'));
      stayFilled = true;
    } else if (nTrip > 1 && stayFilled) {
      var booked = {};
      (d.stays || []).forEach(function (s) { booked[s.date] = true; });
      var open = [];
      for (var k = 1; k < nTrip; k++) {
        var iso = dayToIso(d.start, k);
        if (!booked[iso]) open.push(shortDate(iso));
      }
      if (open.length) stays.appendChild(make('span', 'tc-sub tc-stays__open', open.join(', ') + ' 숙소는 아직 미정'));
    }
    setRow('stay', stays, stayFilled, changed.indexOf('숙소') > -1);

    var pinList = make('span', 'tc-stays');
    (d.pins || []).forEach(function (p, i) {
      var line = make('span', 'tc-stay');
      line.appendChild(make('span', 'tc-stay__date', p.day + '일차'));
      line.appendChild(document.createTextNode(p.name));
      if (p.time) line.appendChild(make('span', 'tc-sub', ' · ' + p.time));
      var x = make('button', 'tc-x', '×');
      x.type = 'button';
      x.setAttribute('aria-label', p.name + ' 빼기');
      x.addEventListener('click', function () { removePin(i); });
      line.appendChild(x);
      pinList.appendChild(line);
    });
    setRow('pins', pinList, (d.pins || []).length > 0, changed.indexOf('추가한 장소') > -1);

    // 필수 항목 진행도
    var total = 4;
    var done = total - state.missing.length;
    el.progress.style.width = Math.round(done / total * 100) + '%';
    el.progressText.textContent = state.ready
      ? '필수 정보를 모두 모았어요'
      : '필수 정보 ' + done + '/' + total;
    el.missing.textContent = state.ready ? '' : '남은 항목: ' + state.missing.join(', ');

    el.notes.textContent = '';
    (state.notes || []).forEach(function (n) { el.notes.appendChild(make('li', null, n)); });
    el.notes.hidden = !(state.notes || []).length;

    el.apply.disabled = !state.ready || state.busy;
    renderPlan();
    updateMap();
  }


  /* ---------- 일정 미리보기 (날짜별 타임라인) ---------- */

  // 일정에 영향을 주는 값이 바뀌었는지 알아보는 표식 (담은 장소/제목은 일정 생성에 영향이 없다)
  function planSig() {
    var d = state.draft;
    var sp = d.start_place;
    return JSON.stringify([
      d.place, d.start, d.end, d.people, d.budget_style, d.budget_total, d.transport, d.categories, d.start_time,
      sp ? [sp.name, sp.lat, sp.lon] : null,
      (d.stays || []).map(function (x) { return [x.date, x.name, x.lat, x.lon, x.arrival_time, x.departure_time]; }),
      (d.pins || []).map(function (p) { return [p.day, p.name, p.time, p.lat, p.lon]; })
    ]);
  }

  function planFresh() {
    return !!(state.plan && state.plan.sig === planSig());
  }

  function currentDay() {
    if (!planFresh()) return null;
    return state.plan.days[Math.min(state.dayTab, state.plan.days.length - 1)] || null;
  }

  // 서버가 짠 일정 + 대화에서 담아 둔 장소(그날 맨 뒤)
  function isGone(day, it) {
    return state.removed.some(function (r) { return r.day === day.day && r.name === it.name; });
  }

  function removedKey() {
    return JSON.stringify([state.removed.map(function (r) { return r.day + ':' + r.name; }).sort(), orderList()]);
  }

  // 서버가 짠 일정(담은 장소 포함)에서 지운 것을 빼고, 사용자가 바꾼 순서대로 보여 준다
  function dayItems(day) {
    var items = (day.items || []).filter(function (it) { return !isGone(day, it); });
    var names = state.order[day.day];

    if (names) {
      var pos = {};
      names.forEach(function (n, i) { if (!(n in pos)) pos[n] = i; });
      items = items.map(function (it, i) { return { it: it, i: i }; })
        .sort(function (a, b) {
          var pa = a.it.name in pos ? pos[a.it.name] : 1000 + a.i;
          var pb = b.it.name in pos ? pos[b.it.name] : 1000 + b.i;
          return pa - pb;
        })
        .map(function (x) { return x.it; });
    }
    return items;
  }

  // 순서 바꾸기: 같은 날 안에서 from 번째 장소를 to 번째로 옮기고, 서버에서 시간을 다시 계산해 온다
  function moveItem(day, from, to) {
    var items = dayItems(day);
    if (from === to || from < 0 || to < 0 || from >= items.length || to >= items.length) return;
    var names = items.map(function (it) { return it.name; });
    var moved = names.splice(from, 1)[0];
    names.splice(to, 0, moved);
    state.order[day.day] = names;
    save();
    renderPlan();
    updateMap();
    refreshSoon();
  }

  function resetOrder(day) {
    delete state.order[day.day];
    save();
    renderPlan();
    updateMap();
    refreshSoon();
  }

  function dayStartPoint(day) {
    if (day.day === 1) {
      var sp = state.draft.start_place;
      return sp && sp.lat != null ? { lat: sp.lat, lon: sp.lon } : null;
    }
    var prev = state.plan.days[day.day - 2];
    var arr = prev ? (prev.items || []) : [];
    for (var i = arr.length - 1; i >= 0; i--) {
      if (arr[i].is_stay && arr[i].lat != null) return { lat: arr[i].lat, lon: arr[i].lon };
    }
    return null;
  }

  // 지운 장소를 목록에서 바로 빼고, 서버에서 시간을 다시 계산해 온다
  function removeItem(day, it) {
    if (it.pin) {
      var idx = -1;
      (state.draft.pins || []).forEach(function (p, i) {
        if (idx < 0 && p.day === day.day && p.name === it.name) idx = i;
      });
      if (idx > -1) removePin(idx);
      return;
    }
    if (isGone(day, it)) return;
    state.removed = state.removed.concat([{ day: day.day, name: it.name }]);
    save();
    renderPlan();
    updateMap();
    refreshSoon();
  }

  function restoreDay(day) {
    state.removed = state.removed.filter(function (r) { return r.day !== day.day; });
    save();
    renderPlan();
    updateMap();
    refreshSoon();
  }

  // 연달아 지울 수 있으니 잠깐 기다렸다가 한 번만 다시 계산한다
  function refreshSoon() {
    clearTimeout(removeTimer);
    removeTimer = setTimeout(function () {
      if (state.ready && planFresh() && state.plan.rkey !== removedKey()) fetchPlan();
    }, 900);
  }

  function planMessage(text, isError) {
    var p = make('p', 'tc-plan__msg' + (isError ? ' is-error' : ''), text);
    el.planBody.appendChild(p);
    return p;
  }

  function renderPlan() {
    el.planTabs.textContent = '';
    el.planBody.textContent = '';
    el.planState.textContent = '';
    el.planRefresh.hidden = !state.ready || state.planBusy;

    if (!state.ready) {
      planMessage('필수 정보를 모두 채우면 날짜별 일정 미리보기가 여기에 나와요.');
      return;
    }

    if (state.planBusy && !planFresh()) {
      var wait = planMessage('일정을 짜는 중이에요... 잠시만 기다려 주세요.');
      wait.className += ' is-loading';
      return;
    }

    if (state.planError) {
      planMessage(state.planError, true);
      return;
    }

    if (!planFresh()) {
      // 곧 새로 만들 예정 (말이 이어지는 동안 잠깐 기다리는 중)
      var soon = planMessage('일정을 짜는 중이에요... 잠시만 기다려 주세요.');
      soon.className += ' is-loading';
      return;
    }

    var days = state.plan.days;
    state.dayTab = Math.min(state.dayTab, days.length - 1);

    days.forEach(function (day, i) {
      var tab = make('button', 'tc-tab' + (i === state.dayTab ? ' is-on' : ''));
      tab.type = 'button';
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', i === state.dayTab ? 'true' : 'false');
      tab.appendChild(make('strong', null, day.day + '일차'));
      tab.appendChild(make('span', null, day.label));
      tab.addEventListener('click', function () {
        state.dayTab = i;
        renderPlan();
        updateMap();
      });
      el.planTabs.appendChild(tab);
    });

    var day = days[state.dayTab];
    var list = make('ol', 'tc-tl');

    // 1) 출발 시간 + 출발점
    var startRow = make('li', 'tc-tl__item is-start');
    startRow.appendChild(make('span', 'tc-tl__time', day.start_time || ''));
    startRow.appendChild(make('span', 'tc-tl__dot'));
    var startBody = make('div', 'tc-tl__body');
    var startHead = make('div', 'tc-tl__head');
    startHead.appendChild(icon('flag'));
    startHead.appendChild(make('strong', null, '출발 · ' + day.start_name));
    startBody.appendChild(startHead);
    startRow.appendChild(startBody);
    list.appendChild(startRow);

    // 2) 그다음 장소들을 순서대로
    var items = dayItems(day);
    var moveSum = 0;
    var reordered = !!state.order[day.day];
    var pending = state.plan.rkey !== removedKey();
    var dragFrom = -1;

    items.forEach(function (it, i) {
      var row = make('li', 'tc-tl__item' + (it.is_stay ? ' is-stay' : '') + (it.pin ? ' is-pin' : ''));
      // 순서를 바꿔서 시간을 다시 계산하는 동안에는 옛 시간을 보여 주지 않는다
      row.appendChild(make('span', 'tc-tl__time', reordered && pending ? '··:··' : (it.arrive || '')));
      row.appendChild(make('span', 'tc-tl__dot', String(i + 1)));

      var body = make('div', 'tc-tl__body');
      var head = make('div', 'tc-tl__head');
      head.appendChild(make('strong', null, it.name));

      if (it.is_stay) {
        var stayTag = make('span', 'tc-tag tc-tag--stay');
        stayTag.appendChild(icon('bed'));
        stayTag.appendChild(document.createTextNode(' 체크인'));
        head.appendChild(stayTag);
      } else if (it.pin) {
        head.appendChild(make('span', 'tc-tag tc-tag--pin', '담은 장소'));
      } else if (it.kind) {
        head.appendChild(make('span', 'tc-tag', it.kind));
      }
      var mv = make('span', 'tc-tl__mv');
      var up = make('button', 'tc-tl__mvbtn', '↑');
      up.type = 'button';
      up.title = '위로';
      up.setAttribute('aria-label', it.name + ' 위로 옮기기');
      up.disabled = i === 0;
      up.addEventListener('click', function () { moveItem(day, i, i - 1); });
      var down = make('button', 'tc-tl__mvbtn', '↓');
      down.type = 'button';
      down.title = '아래로';
      down.setAttribute('aria-label', it.name + ' 아래로 옮기기');
      down.disabled = i === items.length - 1;
      down.addEventListener('click', function () { moveItem(day, i, i + 1); });
      mv.appendChild(up);
      mv.appendChild(down);
      head.appendChild(mv);

      // 끌어서 순서 바꾸기 (컴퓨터)
      row.draggable = items.length > 1;
      row.addEventListener('dragstart', function (e) {
        dragFrom = i;
        row.classList.add('is-drag');
        if (e.dataTransfer) {
          e.dataTransfer.effectAllowed = 'move';
          e.dataTransfer.setData('text/plain', String(i));
        }
      });
      row.addEventListener('dragover', function (e) {
        if (dragFrom < 0) return;
        e.preventDefault();
        row.classList.add('is-over');
      });
      row.addEventListener('dragleave', function () { row.classList.remove('is-over'); });
      row.addEventListener('dragend', function () {
        dragFrom = -1;
        row.classList.remove('is-drag');
        list.querySelectorAll('.is-over').forEach(function (n) { n.classList.remove('is-over'); });
      });
      row.addEventListener('drop', function (e) {
        e.preventDefault();
        var from = dragFrom;
        dragFrom = -1;
        moveItem(day, from, i);
      });

      var del = make('button', 'tc-tl__del', '삭제');
      del.type = 'button';
      del.setAttribute('aria-label', it.name + ' 일정에서 빼기');
      del.addEventListener('click', function () { removeItem(day, it); });
      head.appendChild(del);

      body.appendChild(head);

      var sub = [];
      if (it.move != null) {
        moveSum += it.move;
        sub.push(it.move + '분 이동' + (state.plan.transport ? ' · ' + state.plan.transport + ' 기준' : ''));
      }
      if (it.stay && !it.is_stay) sub.push('체류 ' + it.stay + '분');

      if (sub.length) {
        var meta = make('p', 'tc-tl__meta');
        meta.appendChild(icon('route'));
        meta.appendChild(document.createTextNode(' ' + sub.join(' · ')));
        body.appendChild(meta);
      }

      row.appendChild(body);
      list.appendChild(row);
    });

    el.planBody.appendChild(list);

    var summary = '방문 ' + items.length + '곳';
    if (moveSum) summary += ' · 이동 합계 ' + moveSum + '분';
    if (state.planBusy) summary += ' · 시간을 다시 계산하는 중...';
    el.planState.textContent = summary;

    if (reordered) {
      var ro = make('button', 'tc-link tc-tl__undo', '순서 원래대로');
      ro.type = 'button';
      ro.addEventListener('click', function () { resetOrder(day); });
      el.planState.appendChild(ro);
    }

    var goneToday = state.removed.filter(function (r) { return r.day === day.day; }).length;
    if (goneToday) {
      var undo = make('button', 'tc-link tc-tl__undo', '삭제한 ' + goneToday + '곳 되돌리기');
      undo.type = 'button';
      undo.addEventListener('click', function () { restoreDay(day); });
      el.planState.appendChild(undo);
    }
  }

  // 처음 일정이 나오면 일정 미리보기가 보이도록 패널을 아래로 내려 준다
  function showPlan() {
    var box = el.planBody.closest('.tc-draft__body');
    var section = el.planBody.closest('.tc-plan');
    if (!box || !section || typeof box.scrollTo !== 'function') return;
    box.scrollTo({ top: Math.max(section.offsetTop - box.offsetTop - 8, 0), behavior: 'smooth' });
  }

  function maybePlan(force) {
    clearTimeout(planTimer);

    if (!state.ready) {
      renderPlan();
      return;
    }

    if (!force && planFresh()) {
      renderPlan();
      return;
    }

    // 말이 오가는 중에는 잠깐 기다렸다가 한 번만 만든다
    planTimer = setTimeout(function () { fetchPlan(); }, force ? 0 : 500);
  }

  function fetchPlan() {
    if (state.planBusy || !state.ready || !cfg.previewUrl) return;

    var sig = planSig();
    var rkey = removedKey();
    var firstPlan = false;
    state.planBusy = true;
    state.planError = '';
    renderPlan();

    post(cfg.previewUrl, { draft: state.draft, removed: state.removed, order: orderList() })
      .then(function (data) {
        state.planBusy = false;

        if (data.ok && Array.isArray(data.days)) {
          firstPlan = !state.plan;
          state.plan = { sig: sig, rkey: rkey, days: data.days, transport: data.transport || '' };
          state.planError = '';
          save();
        } else if (data.login) {
          state.planError = '로그인이 풀렸어요. 다시 로그인한 뒤 이어서 해 주세요.';
        } else {
          state.planError = data.error || '일정 미리보기를 만들지 못했어요.';
        }

        // 만드는 동안 초안이 또 바뀌었으면 새로 만든다
        if (state.ready && !state.planError && !planFresh()) {
          maybePlan();
          return;
        }
        if (state.ready && !state.planError && state.plan && state.plan.rkey !== removedKey()) {
          refreshSoon();
        }
        renderPlan();
        updateMap();
        if (firstPlan && state.plan) showPlan();
      }, function () {
        state.planBusy = false;
        state.planError = '네트워크에 문제가 있어요. 다시 시도해 주세요.';
        renderPlan();
      });
  }

  /* ---------- 지도 ---------- */

  var map = null;
  var overlays = [];

  function initMap() {
    if (map || !el.mapBox) return;
    if (!(window.kakao && kakao.maps && kakao.maps.load)) {
      el.mapHint.textContent = '지도를 불러오지 못했어요.';
      el.mapHint.hidden = false;
      return;
    }
    kakao.maps.load(function () {
      map = new kakao.maps.Map(el.mapBox, {
        center: new kakao.maps.LatLng(36.5, 127.8),
        level: 13
      });
      updateMap();
    });
  }

  function pin(kind, label, lat, lon) {
    var wrap = make('div', 'tc-mappin tc-mappin--' + kind);
    wrap.appendChild(make('span', 'tc-mappin__label', label));
    wrap.appendChild(make('span', 'tc-mappin__dot'));
    return new kakao.maps.CustomOverlay({
      position: new kakao.maps.LatLng(lat, lon),
      content: wrap,
      xAnchor: 0.5,
      yAnchor: 1
    });
  }

  function updateMap() {
    if (!map) return;
    overlays.forEach(function (o) { o.setMap(null); });
    overlays = [];

    var d = state.draft;
    var points = [];

    function add(kind, label, lat, lon) {
      if (lat == null || lon == null) return;
      var o = pin(kind, label, lat, lon);
      o.setMap(map);
      overlays.push(o);
      points.push(new kakao.maps.LatLng(lat, lon));
    }

    var day = currentDay();

    if (day) {
      // 일정 미리보기가 있으면 선택한 날의 방문 순서대로 번호를 붙여 보여준다
      var path = [];
      var first = dayStartPoint(day);
      if (first) {
        add('start', '출발 · ' + day.start_name, first.lat, first.lon);
        path.push(new kakao.maps.LatLng(first.lat, first.lon));
      }
      dayItems(day).forEach(function (it, i) {
        if (it.lat == null || it.lon == null) return;
        add(it.is_stay ? 'stay' : 'stop', (i + 1) + '. ' + it.name, it.lat, it.lon);
        path.push(new kakao.maps.LatLng(it.lat, it.lon));
      });
      if (path.length > 1 && kakao.maps.Polyline) {
        var line = new kakao.maps.Polyline({
          path: path, strokeWeight: 4, strokeColor: '#2d6cdf', strokeOpacity: 0.75, strokeStyle: 'solid'
        });
        line.setMap(map);
        overlays.push(line);
      }
    } else {
      if (d.center) add('place', d.place || '여행지', d.center.lat, d.center.lon);
      if (d.start_place) add('start', '출발 · ' + (d.start_place.name || d.start_place.query), d.start_place.lat, d.start_place.lon);
      (d.stays || []).forEach(function (s, i) {
        add('stay', shortDate(s.date) + ' ' + (s.name || s.query), s.lat, s.lon);
      });
    }

    el.mapHint.hidden = points.length > 0;
    if (!points.length) el.mapHint.textContent = '지역을 정하면 지도에 표시돼요.';

    map.relayout();

    if (points.length > 1) {
      var bounds = new kakao.maps.LatLngBounds();
      points.forEach(function (p) { bounds.extend(p); });
      map.setBounds(bounds, 70, 70, 70, 70);
    } else if (points.length === 1) {
      map.setCenter(points[0]);
      map.setLevel(d.start_place || (d.stays || []).length ? 5 : 8);
    }
  }

  /* ---------- 서버 통신 ---------- */

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().catch(function () { return { ok: false, error: '서버 응답을 읽지 못했어요.' }; })
        .then(function (data) { data.status = res.status; return data; });
    });
  }

  function sendMessage(text) {
    text = (text || '').trim();
    if (!text || state.busy) return;

    state.messages.push({ role: 'user', content: text });
    state.busy = true;
    state.notes = [];
    el.input.value = '';
    renderMessages();
    renderDraft();

    var history = state.messages
      .filter(function (m) { return !m.local; })
      .slice(-MAX_SEND)
      .map(function (m) { return { role: m.role, content: m.content }; });

    post(cfg.chatUrl, { messages: history, draft: state.draft })
      .then(function (data) {
        state.busy = false;

        if (!data.ok) {
          // 실패한 메시지는 되돌려서 다시 보낼 수 있게 한다
          state.messages.pop();
          el.input.value = text;
          if (data.login) {
            addBot('로그인이 풀렸어요. 다시 로그인한 뒤 이어서 해 주세요.', true);
          } else {
            addBot(data.error || '대화를 처리하지 못했어요.', true);
          }
          renderMessages();
          renderDraft();
          return;
        }

        state.draft = Object.assign(emptyDraft(), data.draft);
        state.missing = data.missing || [];
        state.ready = !!data.ready;
        state.notes = data.notes || [];
        state.messages.push({ role: 'assistant', content: data.reply, rec: data.recommendation || null });
        save();
        renderMessages();
        renderDraft(data.changed || []);
        maybePlan();
      }, function () {
        state.busy = false;
        state.messages.pop();
        el.input.value = text;
        addBot('네트워크에 문제가 있어요. 연결을 확인하고 다시 보내 주세요.', true);
        renderMessages();
        renderDraft();
      });
  }

  function applyDraft() {
    if (!state.ready || state.busy) return;

    state.busy = true;
    el.apply.disabled = true;
    el.apply.textContent = '';
    el.apply.appendChild(document.createTextNode('일정을 만드는 중...'));
    renderMessages();

    post(cfg.applyUrl, { draft: state.draft, removed: state.removed, order: orderList() })
      .then(function (data) {
        if (data.ok) {
          clearStore();
          return addPinsToSchedule(data).then(function (failed) {
            var warning = data.warning;
            if (failed.length) {
              warning = (warning ? warning + ' ' : '') + '일정에 넣지 못한 장소가 있어요: ' + failed.join(', ') + ' (상세 화면에서 직접 추가해 주세요)';
            }
            if (warning) {
              state.busy = false;
              addBot(warning, true);
              renderMessages();
              var link = make('a', 'tc-go', '만들어진 여행 보러 가기');
              link.href = data.url;
              el.missing.textContent = '';
              el.missing.appendChild(link);
              resetApplyButton();
              return;
            }
            window.location.href = data.url;
          });
        }
        state.busy = false;
        addBot(data.error || '일정을 만들지 못했어요.', true);
        renderMessages();
        resetApplyButton();
        renderDraft();
      }, function () {
        state.busy = false;
        addBot('네트워크에 문제가 있어요. 다시 시도해 주세요.', true);
        renderMessages();
        resetApplyButton();
        renderDraft();
      });
  }

  function dayToIso(startIso, day) {
    var d = parseDate(startIso);
    d.setDate(d.getDate() + day - 1);
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }

  function pad2(n) { return String(n).padStart(2, '0'); }

  // 만들어진 여행의 날짜별 일정에, 대화에서 담아 둔 장소를 하나씩 넣는다.
  // (일정 상세 화면의 '장소 추가'와 같은 기능을 쓴다)
  function addPinsToSchedule(data) {
    var pins = data.pins || [];
    var failed = [];
    if (!pins.length || !cfg.addUrl) return Promise.resolve(failed);

    el.apply.textContent = '';
    el.apply.appendChild(document.createTextNode('장소를 일정에 담는 중...'));

    return pins.reduce(function (chain, p) {
      return chain.then(function () {
        var body = new URLSearchParams({
          travel_id: data.travel_id,
          s_day: dayToIso(data.start, p.day),
          place_name: p.name,
          place_addr: p.addr || '',
          place_kind: p.kind || '',
          place_lat: p.lat,
          place_lon: p.lon
        });
        if (p.time) body.set('arrive_time', p.time);

        return fetch(cfg.addUrl, {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRFToken': cfg.csrf, 'Content-Type': 'application/x-www-form-urlencoded' },
          body: body.toString()
        }).then(function (res) {
          return res.json().catch(function () { return { success: false }; }).then(function (j) {
            if (!res.ok || !j.success) failed.push(p.name);
          });
        }, function () { failed.push(p.name); });
      });
    }, Promise.resolve()).then(function () { return failed; });
  }

  function resetApplyButton() {
    el.apply.textContent = '';
    el.apply.appendChild(icon('check'));
    el.apply.appendChild(document.createTextNode(' 이 일정 적용하기'));
  }

  /* ---------- 이벤트 ---------- */

  el.form.addEventListener('submit', function (e) {
    e.preventDefault();
    sendMessage(el.input.value);
  });

  // 한글 입력 중(조합 중)의 Enter 는 무시한다.
  el.input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && e.keyCode !== 229) {
      e.preventDefault();
      sendMessage(el.input.value);
    }
  });

  EXAMPLES.forEach(function (text) {
    var b = make('button', 'tc-example', text);
    b.type = 'button';
    b.addEventListener('click', function () { sendMessage(text); });
    el.examples.appendChild(b);
  });

  el.apply.addEventListener('click', applyDraft);

  el.planRefresh.addEventListener('click', function () {
    state.planError = '';
    maybePlan(true);
  });

  el.edit.addEventListener('click', function () {
    el.input.focus();
    el.input.placeholder = '바꾸고 싶은 내용을 말해 주세요. 예) 숙소는 해운대 쪽으로 바꿔줘';
    if (window.matchMedia('(max-width: 859px)').matches) {
      el.form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });

  el.reset.addEventListener('click', function () {
    if (state.busy) return;
    clearStore();
    start(false);
  });

  /* ---------- 시작 ---------- */

  function start(allowRestore) {
    state.messages = [];
    state.draft = emptyDraft();
    state.missing = ['여행 지역', '출발일', '종료일', '여행 컨셉'];
    state.ready = false;
    state.notes = [];
    state.busy = false;
    state.plan = null;
    state.removed = [];
    state.order = {};
    state.planBusy = false;
    state.planError = '';
    state.dayTab = 0;
    clearTimeout(planTimer);

    var restored = allowRestore && load();

    if (!restored) {
      if (BUDGET[cfg.budget]) state.draft.budget_style = cfg.budget;
      state.messages.push({ role: 'assistant', content: WELCOME, local: true });
    }

    el.input.placeholder = '여행 이야기를 편하게 적어 주세요';
    resetApplyButton();
    renderMessages();
    renderDraft();
    if (restored) maybePlan();

    // 메인 화면에서 입력해 온 문장이 있으면 바로 첫 질문으로 보낸다.
    if (!restored && allowRestore && cfg.prefill) {
      sendMessage(cfg.prefill);
    }
  }

  start(true);
  initMap();
})();
