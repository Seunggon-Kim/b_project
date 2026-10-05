/*
 * 그래프(인포그래픽) 공용 툴팁입니다. 흰 바탕(다크 모드는 카드 색)과 사이트 글꼴로 보여 줍니다(evan).
 *
 * 쓰는 법: 페이지에 이 파일을 싣고, 툴팁을 띄울 요소에 data-tip="보여 줄 글자"를 둡니다.
 * 글은 줄바꿈으로 나눕니다: 첫 줄 제목(굵게), 둘째 줄 내용, 셋째 줄부터 흐린 글씨(선수 통계 표 툴팁과 같은 모양).
 * SVG 요소(circle 등)와 HTML 요소 모두 됩니다. 브라우저 기본 툴팁(SVG <title>, title 속성)은
 * 색과 글꼴을 바꿀 수 없어서 이것으로 바꿉니다.
 * 마우스는 올리면 보이고, 터치는 누르면 보이며 다른 곳을 누르면 사라집니다.
 * 키보드로 갈 수 있는 요소(tabindex)는 초점을 받으면 보입니다.
 *
 * Chart.js 그래프는 ChartTip.chartjs() 를 options.plugins.tooltip 에 펼쳐 넣으면 같은 모양이 됩니다.
 * .pa-help 처럼 CSS 로 따로 그리는 도움말(data-tip + ::after)은 건드리지 않습니다.
 */
(function (root) {
  'use strict';
  if (root.ChartTip) return;
  const doc = root.document;
  const SEL = '[data-tip]:not(.pa-help)';
  // 선수·팀 통계 표 머리글 툴팁(css/stats.css .tip-box)과 같은 모양입니다(evan 레퍼런스).
  const CSS = '.chart-tip{position:fixed;z-index:10000;display:none;max-width:300px;padding:0.5rem 0.7rem;'
    + 'border-radius:8px;background:var(--bg-secondary,#fff);color:var(--text-primary,#0f172a);'
    + 'border:1px solid var(--border-color,rgba(15,23,42,0.12));box-shadow:0 6px 20px rgba(0,0,0,0.12);'
    + 'font-family:inherit;font-size:0.82rem;line-height:1.45;white-space:normal;pointer-events:none;}'
    + '.chart-tip b{display:block;margin-bottom:2px;}.chart-tip span{display:block;}'
    + '.chart-tip .f{display:block;margin-top:4px;color:var(--text-muted,#64748b);}';

  let tip = null, current = null;

  function ensure() {
    if (tip) return tip;
    const st = doc.createElement('style');
    st.textContent = CSS;
    doc.head.appendChild(st);
    tip = doc.createElement('div');
    tip.className = 'chart-tip';
    tip.setAttribute('role', 'tooltip');
    doc.body.appendChild(tip);
    return tip;
  }

  /** 커서(x, y) 오른쪽 아래에 두되, 화면 끝에 닿으면 반대쪽으로 넘깁니다. */
  function place(x, y) {
    const w = tip.offsetWidth, h = tip.offsetHeight, vw = root.innerWidth, vh = root.innerHeight;
    let left = x + 14, top = y + 14;
    if (left + w > vw - 8) left = x - w - 14;
    if (top + h > vh - 8) top = y - h - 14;
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = Math.max(8, top) + 'px';
  }

  function show(el, x, y) {
    const text = el.getAttribute('data-tip');
    if (!text) return;
    ensure();
    current = el;
    // 줄바꿈으로 나눈 글: 첫 줄 제목(굵게), 둘째 줄 내용, 셋째 줄부터 흐린 글씨입니다.
    tip.textContent = '';
    text.split('\n').forEach(function (line, i) {
      const node = doc.createElement(i === 0 ? 'b' : 'span');
      if (i >= 2) node.className = 'f';
      node.textContent = line;
      tip.appendChild(node);
    });
    tip.style.display = 'block';
    if (x === undefined) {
      const r = el.getBoundingClientRect();
      x = r.left + r.width / 2; y = r.top + r.height / 2;
    }
    place(x, y);
  }

  function hide() {
    current = null;
    if (tip) tip.style.display = 'none';
  }

  function find(target) {
    return target && target.closest ? target.closest(SEL) : null;
  }

  doc.addEventListener('mouseover', function (e) {
    const el = find(e.target);
    if (el) show(el, e.clientX, e.clientY);
  });
  doc.addEventListener('mousemove', function (e) {
    if (current && tip) place(e.clientX, e.clientY);
  });
  doc.addEventListener('mouseout', function (e) {
    if (!current) return;
    const to = find(e.relatedTarget);
    if (to !== current) hide();
  });
  // 키보드로 옮긴 초점(:focus-visible)일 때만 보입니다. 마우스로 고르기 칸을 누를 때는 목록을 가리지 않게 띄우지 않습니다.
  doc.addEventListener('focusin', function (e) {
    const el = find(e.target);
    let kb = true;
    try { kb = el ? el.matches(':focus-visible') : false; } catch (err) { kb = true; }
    if (el && kb) show(el); else hide();
  });
  doc.addEventListener('mousedown', hide);
  doc.addEventListener('focusout', hide);
  // 터치: 누르면 보이고, 같은 것을 다시 누르거나 다른 곳을 누르면 사라집니다.
  doc.addEventListener('click', function (e) {
    const el = find(e.target);
    if (!el) { hide(); return; }
    if (e.pointerType === 'mouse') return;
    if (current === el && tip && tip.style.display === 'block') hide(); else show(el);
  });
  root.addEventListener('scroll', hide, { passive: true });

  /**
   * Chart.js tooltip 옵션입니다(4.x, 툴팁 색·글꼴은 scriptable).
   * 값 대신 함수로 주어서, 툴팁이 뜰 때마다 지금 테마 색과 사이트 글꼴을 읽습니다.
   * 그래서 다크/라이트를 바꾼 뒤 그래프를 다시 그리지 않아도 툴팁 색이 따라갑니다.
   */
  function chartjs() {
    const v = function (n, d) {
      return function () { return (root.getComputedStyle(doc.documentElement).getPropertyValue(n) || '').trim() || d; };
    };
    const font = function (weight) {
      return function () {
        const f = { family: root.getComputedStyle(doc.body).fontFamily };
        if (weight) f.weight = weight;
        return f;
      };
    };
    return {
      backgroundColor: v('--bg-secondary', '#ffffff'),
      titleColor: v('--text-primary', '#0f172a'),
      bodyColor: v('--text-primary', '#0f172a'),
      footerColor: v('--text-muted', '#64748b'),
      borderColor: v('--border-color', 'rgba(15,23,42,0.12)'),
      borderWidth: 1,
      cornerRadius: 8,
      padding: 10,
      titleFont: font('700'),
      bodyFont: font(),
      footerFont: font(),
    };
  }

  root.ChartTip = { show: show, hide: hide, chartjs: chartjs };
})(window);
