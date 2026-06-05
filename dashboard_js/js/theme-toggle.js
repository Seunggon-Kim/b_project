/**
 * C - Baseball Research Center 다크/라이트 모드 토글
 * 모든 페이지의 기본 설정. localStorage('kbo-theme-v2')로 보존.
 *
 * 사용:
 *   1. <link rel="stylesheet" href="...style.css"> 다음에 이 파일 include
 *   2. nav element 자동 탐지 → toggle 버튼 inject
 *
 * Theme 정의:
 *   default: light (style.css의 :root)
 *   data-theme="dark": dark variables override
 */
(function () {
    // 1. 페이지 로드 즉시 theme 적용 (FOUC 방지)
    const stored = localStorage.getItem('kbo-theme-v2') || 'light';
    document.documentElement.setAttribute('data-theme', stored);

    // 2. nav에 toggle 버튼 inject
    function injectButton() {
        const nav = document.querySelector('.nav') || document.querySelector('header nav');
        if (!nav || nav.querySelector('.theme-toggle')) return;

        const btn = document.createElement('button');
        btn.className = 'theme-toggle';
        btn.type = 'button';
        btn.setAttribute('aria-label', 'Toggle theme');
        btn.style.cssText = [
            'background: var(--bg-glass)',
            'border: 1px solid var(--border-color)',
            'color: var(--text-primary)',
            'padding: 0.45rem 0.85rem',
            'border-radius: 8px',
            'cursor: pointer',
            'font-size: 0.9rem',
            'font-family: inherit',
            'margin-left: 0.75rem',
            'transition: all 0.2s ease',
            'display: inline-flex',
            'align-items: center',
            'gap: 0.4rem',
        ].join(';');

        const updateLabel = () => {
            const cur = document.documentElement.getAttribute('data-theme');
            btn.innerHTML = cur === 'dark' ? '<span class="material-symbols-outlined">light_mode</span> Light' : '<span class="material-symbols-outlined">dark_mode</span> Dark';
        };
        updateLabel();

        btn.addEventListener('click', () => {
            const cur = document.documentElement.getAttribute('data-theme');
            const next = cur === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('kbo-theme-v2', next);
            updateLabel();
        });

        btn.addEventListener('mouseenter', () => {
            btn.style.background = 'var(--bg-tertiary)';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.background = 'var(--bg-glass)';
        });

        nav.appendChild(btn);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectButton);
    } else {
        injectButton();
    }
})();
