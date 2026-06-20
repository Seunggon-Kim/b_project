/**
 * Baseball Estudiar — 반응형 내비게이션(햄버거)
 *
 * 좁은 화면에서 상단 nav를 햄버거 버튼으로 접고, 클릭하면 드롭다운으로 펼칩니다.
 * 모든 페이지의 <head>에서 theme-toggle.js 다음에 include 합니다.
 *
 * 점진적 향상(progressive enhancement):
 *   - 실행되면 <html>에 'nav-js' 클래스를 추가합니다.
 *   - 접기 CSS(style.css)는 .nav-js 가 있을 때만 동작하므로,
 *     스크립트가 없거나 실패한 페이지는 기존 줄바꿈 nav가 그대로 노출됩니다(내비 유실 없음).
 */
(function () {
    // 1) JS 사용 표시 — paint 전에 추가해 깜빡임(FOUC) 방지
    document.documentElement.classList.add('nav-js');

    function initNavToggle() {
        const header = document.querySelector('.header');
        const content = header && header.querySelector('.header-content');
        const nav = content && content.querySelector('.nav');
        if (!header || !content || !nav) return;
        if (content.querySelector('.nav-toggle')) return; // 중복 주입 방지

        nav.id = nav.id || 'primary-nav';

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'nav-toggle';
        btn.setAttribute('aria-controls', nav.id);
        btn.setAttribute('aria-expanded', 'false');
        btn.setAttribute('aria-label', '메뉴 열기');
        btn.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">menu</span>';
        const icon = btn.querySelector('.material-symbols-outlined');

        const setOpen = (open) => {
            nav.classList.toggle('open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
            btn.setAttribute('aria-label', open ? '메뉴 닫기' : '메뉴 열기');
            icon.textContent = open ? 'close' : 'menu';
        };

        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            setOpen(!nav.classList.contains('open'));
        });

        // nav 링크 클릭 시 닫기
        nav.addEventListener('click', (e) => {
            if (e.target.closest('.nav-link')) setOpen(false);
        });

        // 메뉴 바깥 클릭 시 닫기
        document.addEventListener('click', (e) => {
            if (nav.classList.contains('open') && !header.contains(e.target)) setOpen(false);
        });

        // Esc 로 닫기
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && nav.classList.contains('open')) {
                setOpen(false);
                btn.focus();
            }
        });

        // 데스크톱 폭으로 넓어지면 열림 상태 초기화
        const wide = window.matchMedia('(min-width: 769px)');
        const onWide = () => { if (wide.matches) setOpen(false); };
        if (wide.addEventListener) wide.addEventListener('change', onWide);
        else if (wide.addListener) wide.addListener(onWide);

        // 로고 다음(맨 끝)에 버튼 배치 — 모바일에서 nav는 절대배치되어 흐름에서 빠짐
        content.appendChild(btn);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavToggle);
    } else {
        initNavToggle();
    }
})();
