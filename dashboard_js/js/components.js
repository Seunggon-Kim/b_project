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
