// UI Components and Helper Functions

/**
 * Format number with commas
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString('ko-KR');
}

/**
 * 외국인 선수 여부 판정.
 * KBO 외국인 선수는 신인 드래프트가 아니라 '자유선발'·'부상 대체 외국인선수'(향후 '아시아쿼터' 포함)로
 * 입단하며, 그 표기가 players.draft_order/draft_year에 그대로 남는다. 국내 선수는 연봉·계약금이 원,
 * 외국인 선수는 달러 단위로 저장되어 있어 통화 표기의 기준으로 쓴다.
 * (검증: 전체 585명 중 43명이 이 신호로 분류 → 저장 연봉이 외국인 ≤160만, 국내 ≥1,500만으로 완전 분리)
 */
function isForeignPlayer(player) {
    if (!player) return false;
    const draft = `${player.draft_order || ''} ${player.draft_year || ''}`;
    return draft.includes('자유선발') || draft.includes('외국인선수') || draft.includes('아시아쿼터');
}

/**
 * Format money. 국내 선수 연봉/계약금은 원, 외국인 선수는 달러 단위로 저장되어 있어 통화를 구분한다.
 * @param {number} amount 금액
 * @param {('KRW'|'USD')} [currency='KRW'] 통화 (USD면 '달러', 그 외 '원')
 */
function formatMoney(amount, currency = 'KRW') {
    if (!amount) return '-';
    const unit = currency === 'USD' ? '달러' : '원';
    return `${formatNumber(amount)}${unit}`;
}

/**
 * Format batting average (3 decimals)
 */
function formatAverage(avg) {
    if (avg === null || avg === undefined) return '-';
    return avg.toFixed(3);
}

/**
 * Format ERA (2 decimals)
 */
function formatERA(era) {
    if (era === null || era === undefined) return '-';
    return era.toFixed(2);
}

/**
 * Format birthday
 */
function formatBirthday(birthday) {
    if (!birthday) return '-';
    // Ensure string
    const bStr = birthday.toString();
    const year = bStr.substring(0, 4);
    const month = bStr.substring(4, 6);
    const day = bStr.substring(6, 8);
    return `${year}년 ${month}월 ${day}일`;
}

/**
 * Format throw/bat
 */
function formatThrowBat(throwHand, batHand) {
    const throwMap = { 'R': '우투', 'L': '좌투', 'S': '양투' };
    const batMap = { 'R': '우타', 'L': '좌타', 'S': '양타' };
    const throwText = throwMap[throwHand] || '-';
    const batText = batMap[batHand] || '-';
    return `${throwText}/${batText}`;
}

/**
 * Create stat card component
 */
function createStatCard(label, value, delta, icon) {
    return `
        <div class="stat-card fade-in">
            <div class="stat-icon">${icon}</div>
            <div class="stat-label">${label}</div>
            <div class="stat-value">${value}</div>
            ${delta ? `<div class="stat-delta">↗ ${delta}</div>` : ''}
        </div>
    `;
}

/**
 * Create loading spinner
 */
function createLoadingSpinner() {
    return `
        <div class="loading">
            <div class="spinner"></div>
        </div>
    `;
}

/**
 * Create error message
 */
function createErrorMessage(message) {
    return `
        <div class="card">
            <div class="card-body text-center">
                <h3><span class="material-symbols-outlined">warning</span> 오류</h3>
                <p>${message}</p>
            </div>
        </div>
    `;
}

/**
 * Create empty state message
 */
function createEmptyState(message) {
    return `
        <div class="card">
            <div class="card-body text-center">
                <h3><span class="material-symbols-outlined">inbox</span> 데이터 없음</h3>
                <p>${message}</p>
            </div>
        </div>
    `;
}

/**
 * Create badge
 */
function createBadge(text, type = 'primary') {
    return `<span class="badge badge-${type}">${text}</span>`;
}

/**
 * HTML 이스케이프 — 텍스트를 안전하게 마크업에 삽입
 */
function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

/**
 * 선수 이름 -> 선수 분석(player-analytics) 딥링크.
 * id 없으면 링크 없이 일반 텍스트. 페이지 위치(root vs /pages/)에 맞춰 경로 자동 결정.
 */
function playerLink(name, id, cls) {
    const text = escapeHtml(name);
    if (id === null || id === undefined || id === '') return text;
    const base = window.location.pathname.includes('/pages/') ? '' : 'pages/';
    const klass = cls ? `player-link ${cls}` : 'player-link';
    return `<a class="${klass}" href="${base}player-analytics?id=${encodeURIComponent(id)}">${text}</a>`;
}

/**
 * Create table from data
 */
function createTable(headers, rows) {
    const headerHTML = headers.map(h => `<th>${h}</th>`).join('');
    const rowsHTML = rows.map(row => {
        const cells = row.map(cell => `<td>${cell}</td>`).join('');
        return `<tr>${cells}</tr>`;
    }).join('');

    return `
        <div class="table-container">
            <table class="table">
                <thead>
                    <tr>${headerHTML}</tr>
                </thead>
                <tbody>
                    ${rowsHTML}
                </tbody>
            </table>
        </div>
    `;
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    // Simple alert for now - can be enhanced with toast notifications
    alert(message);
}

/**
 * Debounce function for search
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Set active navigation link
 */
function setActiveNav(pageName) {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === pageName ||
            (pageName === 'index.html' && link.getAttribute('href') === './')) {
            link.classList.add('active');
        }
    });
}

/**
 * Initialize page
 */
function initializePage() {
    // Set active nav based on current page
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    setActiveNav(currentPage);

    // Add smooth scroll behavior
    document.documentElement.style.scrollBehavior = 'smooth';
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializePage);
} else {
    initializePage();
}

/**
 * Format Innings Pitched (IP)
 */
function formatIP(ip) {
    if (ip === null || ip === undefined) return '-';
    const val = parseFloat(ip);
    if (isNaN(val)) return ip;
    return val.toFixed(1);
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        formatNumber,
        formatMoney,
        isForeignPlayer,
        formatAverage,
        formatERA,
        formatIP,
        formatBirthday,
        formatThrowBat,
        createStatCard,
        createLoadingSpinner,
        createErrorMessage,
        createEmptyState,
        createBadge,
        createTable,
        escapeHtml,
        playerLink,
        showNotification,
        debounce,
        setActiveNav
    };
}

/**
 * 구단 색입니다. 화면 여러 곳이 같은 값을 봐야 합니다.
 *
 * 선수 분석 안에만 있던 표를 옮겼습니다. 팀 기록실이 같은 색을 써야
 * 하는데, 복사해 두면 한쪽만 고쳤을 때 두 화면 색이 달라집니다.
 *
 * 우리 자료에 실제로 있는 팀을 전부 넣습니다. 기록에 남은 소속을
 * 전수조사하니 23개였습니다(1982~2026).
 *
 * **없어진 구단은 계보를 이은 구단 색을 씁니다.** 다만 이어지지 않는
 * 것도 있습니다.
 *
 *     삼미 -> 청보 -> 태평양 -> 현대     여기서 끝입니다(2007 해체)
 *     우리 -> 히어로즈 -> 넥센 -> 키움    2008 창단, 현대와 별개입니다
 *     쌍방울                            1999 로 끝입니다
 *     SK -> SSG                        2000 창단, 쌍방울과 별개입니다
 *     MBC -> LG        OB -> 두산
 *     빙그레 -> 한화    해태 -> KIA
 */
const TEAM_COLORS = {
    // 현재 1군 구단
    '키움': '#570514',
    '두산': '#1A1748',
    '롯데': '#041E42',
    '삼성': '#074CA1',
    '한화': '#FC4E00',
    'KIA': '#EA0029',
    'LG': '#C30452',
    'SSG': '#CE0E2D',
    'NC': '#315288',
    'KT': '#000000',

    // 퓨처스 전용 구단
    '고양': '#570514',
    '울산': '#8B0000',
    '상무': '#EAB146',
    '경찰': '#333336',

    // 없어진 구단
    'SK': '#CE0E2D',
    '넥센': '#570514',
    '히어로즈': '#570514',
    '우리': '#570514',
    '해태': '#EA0029',
    'OB': '#1A1748',
    '빙그레': '#FC4E00',
    'MBC': '#0B4EA2',
    '현대': '#003F87',
    '쌍방울': '#005BAC',
    '태평양': '#0067A3',
    '청보': '#E4002B',
    '삼미': '#003DA5',
};

/** 팀 이름에 맞는 색입니다. 못 찾으면 기본 남색입니다. */
function teamColor(teamName) {
    if (!teamName) return '#1e293b';
    for (const [name, color] of Object.entries(TEAM_COLORS)) {
        if (String(teamName).includes(name)) return color;
    }
    return '#1e293b';
}

/**
 * 팀 이름 -> franchise_id 입니다.
 *
 * 팀 기록실 링크를 걸 때 씁니다. 정본은 D1 `team_seasons` 이고 여기는
 * 화면에서 링크를 만들기 위한 사본입니다. 옛 이름도 넣어 두어야
 * 1982년 표에서도 링크가 걸립니다.
 *
 * **이어지지 않는 것에 주의하십시오.** 현대(HD)와 키움(WO)은 다른
 * 구단이고, 쌍방울(SB)과 SSG(SK)도 다릅니다.
 */
const FRANCHISE_BY_TEAM = {
    // 현재 구단
    KIA: 'HT', 삼성: 'SS', LG: 'LG', 두산: 'OB', 롯데: 'LT',
    한화: 'HH', SSG: 'SK', 키움: 'WO', NC: 'NC', KT: 'KT',
    // 옛 이름
    해태: 'HT', MBC: 'LG', OB: 'OB', 빙그레: 'HH', SK: 'SK',
    넥센: 'WO', 히어로즈: 'WO', 우리: 'WO',
    // 없어진 구단
    삼미: 'HD', 청보: 'HD', 태평양: 'HD', 현대: 'HD', 쌍방울: 'SB',
};

/** 팀 기록실 주소입니다. 모르는 팀이면 null 입니다. */
function teamRecordHref(teamName, prefix) {
    const id = FRANCHISE_BY_TEAM[String(teamName || '').trim()];
    if (!id) return null;
    return `${prefix || ''}team-record?id=${id}`;
}
