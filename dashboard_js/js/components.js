// UI Components and Helper Functions

/**
 * Format number with commas
 */
function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    return num.toLocaleString('ko-KR');
}

/**
 * Format money (KRW)
 */
function formatMoney(amount) {
    if (!amount) return '-';
    return `${formatNumber(amount)}원`;
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
        showNotification,
        debounce,
        setActiveNav
    };
}
