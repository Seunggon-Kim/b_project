// API Configuration and Helper Functions
// 주소는 js/config.js 가 정합니다. 이 파일보다 먼저 로드되어야 합니다.
const API_BASE_URL = window.KBO_API_BASE;

class API {
    /**
     * Fetch dashboard statistics
     */
    static async getDashboardStats() {
        try {
            const response = await fetch(`${API_BASE_URL}/dashboard/stats`);
            if (!response.ok) throw new Error('Failed to fetch dashboard stats');
            return await response.json();
        } catch (error) {
            console.error('Error fetching dashboard stats:', error);
            throw error;
        }
    }

    /**
     * Fetch teams list
     */
    static async getTeams() {
        try {
            const response = await fetch(`${API_BASE_URL}/teams`);
            if (!response.ok) throw new Error('Failed to fetch teams');
            return await response.json();
        } catch (error) {
            console.error('Error fetching teams:', error);
            throw error;
        }
    }

    /**
     * Search players
     */
    static async searchPlayers(query) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error('Failed to search players');
            return await response.json();
        } catch (error) {
            console.error('Error searching players:', error);
            throw error;
        }
    }

    /**
     * Get player info
     */
    static async getPlayerInfo(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}`);
            if (!response.ok) throw new Error('Failed to fetch player info');
            return await response.json();
        } catch (error) {
            console.error('Error fetching player info:', error);
            throw error;
        }
    }

    /**
     * Get player news
     */
    static async getPlayerNews(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/news`);
            if (!response.ok) throw new Error('Failed to fetch player news');
            return await response.json();
        } catch (error) {
            console.error('Error fetching player news:', error);
            return { news: [] };
        }
    }

    /**
     * Get Pitch Arsenal
     */
    static async getPitchArsenal(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/arsenal`);
            if (!response.ok) throw new Error('Failed to fetch pitch arsenal');
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch arsenal:', error);
            // Return empty to prevent UI crash
            return { arsenal: [] };
        }
    }

    /**
     * Get Pitch Usage (By Stands)
     */
    static async getPitchUsage(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/usage`);
            if (!response.ok) throw new Error('Failed to fetch pitch usage');
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch usage:', error);
            return { usage: [] };
        }
    }

    /**
     * Get available seasons (시즌 통계가 존재하는 시즌 목록)
     */
    static async getSeasons() {
        try {
            const response = await fetch(`${API_BASE_URL}/stats/seasons`);
            if (!response.ok) throw new Error('Failed to fetch seasons');
            return await response.json();
        } catch (error) {
            console.error('Error fetching seasons:', error);
            return { seasons: [] };
        }
    }

    /**
     * Get per-season regulation thresholds (규정타석/규정이닝)
     * 시즌별 { team_games, qual_pa, qual_ip } 맵을 반환합니다. 실패 시 빈 객체.
     */
    static async getRegulation() {
        try {
            const response = await fetch(`${API_BASE_URL}/stats/regulation`);
            if (!response.ok) throw new Error('Failed to fetch regulation');
            return await response.json();
        } catch (error) {
            console.error('Error fetching regulation:', error);
            return { regulation: {} };
        }
    }

    /**
     * Get batter statistics
     * Added min_pa support
     */
    static async getBatterStats(season = 2025, limit = 100, min_pa = 0, teamIds = null) {
        try {
            let url = `${API_BASE_URL}/stats/batters?season=${season}&limit=${limit}&min_pa=${min_pa}`;
            if (teamIds) url += `&team_ids=${encodeURIComponent(teamIds)}`;
            console.log('Fetching batter stats:', url);

            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch batter stats');
            return await response.json();
        } catch (error) {
            console.error('Error fetching batter stats:', error);
            throw error;
        }
    }

    /**
     * Get pitcher statistics
     * Added min_ip support
     */
    static async getPitcherStats(season = 2025, limit = 100, min_ip = 0, teamIds = null) {
        try {
            let url = `${API_BASE_URL}/stats/pitchers?season=${season}&limit=${limit}&min_ip=${min_ip}`;
            if (teamIds) url += `&team_ids=${encodeURIComponent(teamIds)}`;
            console.log('Fetching pitcher stats:', url);

            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch pitcher stats');
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitcher stats:', error);
            throw error;
        }
    }

    /**
     * Get games list
     */
    static async getGames(season = 2025, limit = 50) {
        try {
            const response = await fetch(`${API_BASE_URL}/games?season=${season}&limit=${limit}`);
            if (!response.ok) throw new Error('Failed to fetch games');
            return await response.json();
        } catch (error) {
            console.error('Error fetching games:', error);
            throw error;
        }
    }

    /**
     * Get KBO team standings (koreabaseball.com 공식 TeamRank 스크래핑)
     */
    static async getStandings() {
        try {
            const response = await fetch(`${API_BASE_URL}/standings`);
            if (!response.ok) throw new Error('Failed to fetch standings');
            return await response.json();
        } catch (error) {
            console.error('Error fetching standings:', error);
            throw error;
        }
    }

    /**
     * Get KBO individual leaders (타자: 타율/OPS/wRC+, 투수: ERA/이닝/탈삼진)
     */
    static async getLeaders(season) {
        try {
            const url = season ? `${API_BASE_URL}/leaders?season=${season}` : `${API_BASE_URL}/leaders`;
            const response = await fetch(url);
            if (!response.ok) throw new Error('Failed to fetch leaders');
            return await response.json();
        } catch (error) {
            console.error('Error fetching leaders:', error);
            throw error;
        }
    }

    /**
     * DB Explorer: 전체 테이블 목록 (행/컬럼 수 포함)
     */
    static async getDbTables() {
        const response = await fetch(`${API_BASE_URL}/db/tables`);
        if (!response.ok) throw new Error('Failed to fetch tables');
        return await response.json();
    }

    /**
     * DB Explorer: 단일 테이블 스키마 + 페이지네이션 데이터
     */
    static async getDbTable(name, limit = 50, offset = 0) {
        const url = `${API_BASE_URL}/db/table/${encodeURIComponent(name)}?limit=${limit}&offset=${offset}`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to fetch table data');
        return await response.json();
    }

    /**
     * DB Explorer: 테이블 전체 CSV 다운로드 URL
     */
    static dbCsvUrl(name) {
        return `${API_BASE_URL}/db/table/${encodeURIComponent(name)}/csv`;
    }

    /**
     * 수집 작업이 마지막으로 언제 돌았는지.
     *
     * 예전에는 서버 cron 이 15분마다 다시 쓰던 정적 파일
     * (`cron_status.json`)을 읽었습니다. 이제 서버가 없고 Pages 는
     * 정적 호스팅이라 실행 중에 파일을 못 바꿉니다. GitHub Actions 가
     * D1 에 기록하고 Worker 가 읽어 줍니다.
     */
    static async getJobsStatus() {
        const response = await fetch(`${API_BASE_URL}/jobs/status`, { cache: 'no-store' });
        if (!response.ok) throw new Error('Failed to fetch jobs status');
        return await response.json();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
