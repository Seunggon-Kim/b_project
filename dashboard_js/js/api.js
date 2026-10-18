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
    // season 을 주면 그 시즌에 실제로 있던 팀을 받습니다. 안 주면
    // 예전처럼 현재 10팀입니다. 1982 에는 삼미·MBC 가 있고 KT·NC·
    // 키움이 없어, 시즌을 안 넘기면 있지도 않은 팀으로 거르게 됩니다.
    static async getTeams(season) {
        try {
            const q = season ? `?season=${encodeURIComponent(season)}` : '';
            const response = await fetch(`${API_BASE_URL}/teams${q}`);
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
     *
     * **404 면 null 입니다.** 오류가 아니라 "1군 기록이 한 번도 없는
     * 선수" 라는 뜻입니다. 부르는 쪽이 "찾을 수 없습니다" 로 보여 줍니다.
     */
    static async getPlayerInfo(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}`);
            if (response.status === 404) return null;
            if (!response.ok) throw new Error('Failed to fetch player info');
            return await response.json();
        } catch (error) {
            console.error('Error fetching player info:', error);
            throw error;
        }
    }

    /**
     * Get Pitch Arsenal
     * season 을 주면 그 시즌, 안 주면 서버 기본(올해)입니다.
     */
    static async getPitchArsenal(playerId, season) {
        try {
            const q = season ? `?season=${encodeURIComponent(season)}` : '';
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/arsenal${q}`);
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
     * season 을 주면 그 시즌, 안 주면 서버 기본(올해)입니다.
     */
    static async getPitchUsage(playerId, season) {
        try {
            const q = season ? `?season=${encodeURIComponent(season)}` : '';
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/usage${q}`);
            if (!response.ok) throw new Error('Failed to fetch pitch usage');
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch usage:', error);
            return { usage: [] };
        }
    }

    /**
     * 투수 손별 리그 평균 무브먼트(/stats/movement_avg). 없거나 실패하면 rows 가 빈 배열입니다.
     */
    static async getMovementAvg(season) {
        try {
            const response = await fetch(`${API_BASE_URL}/stats/movement_avg?season=${encodeURIComponent(season)}`);
            if (!response.ok) return { rows: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching movement average:', error);
            return { rows: [] };
        }
    }

    /** 투수 구종 가치(득점 가치). 운영에 아직 없으면 빈 결과입니다. */
    static async getPitchValues(playerId, season) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/pitch_values?season=${encodeURIComponent(season)}`);
            if (!response.ok) return { rows: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch values:', error);
            return { rows: [] };
        }
    }

    /** 시즌별 구종 추이 합계(시즌 × 구종 × 타자 손 × 카운트). 없거나 실패하면 빈 rows. */
    static async getPitchTrend(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/pitch_trend`);
            if (!response.ok) return { rows: [], values: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch trend:', error);
            return { rows: [], values: [] };
        }
    }

    /** 시즌별 구종 추이 합계를 볼카운트(bc '0-0'…'3-2')까지 나눠 받습니다(?by=count). 묶음 cnt·hbp·sf 도 들어 있습니다. */
    static async getPitchTrendByCount(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/pitch_trend?by=count`);
            if (!response.ok) return { rows: [], values: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch trend by count:', error);
            return { rows: [], values: [] };
        }
    }

    /** KBO 리그 Plate Discipline 시즌 합계(2016~, 매일 미리 계산). 없거나 실패하면 빈 seasons. */
    static async getPlateDisciplineLeague() {
        try {
            const response = await fetch(`${API_BASE_URL}/stats/plate_discipline`);
            if (!response.ok) return { seasons: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching league plate discipline:', error);
            return { seasons: [] };
        }
    }

    /** 그 시즌 모든 타자의 Batting Run Value·선구 개수입니다(타자 Percentile Rankings). 2016 전·실패면 빈 rows. */
    static async getBatterValues(season) {
        try {
            const response = await fetch(`${API_BASE_URL}/stats/batter_values?season=${encodeURIComponent(season)}`);
            if (!response.ok) return { rows: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching batter values:', error);
            return { rows: [] };
        }
    }

    /** 월·경기 단위 구종 추이입니다(by = 'month' | 'game'). 응답은 cols(키 목록) + rows(값 배열) 모양입니다. */
    static async getPitchTrendPeriod(playerId, by) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/pitch_trend?by=${encodeURIComponent(by)}`);
            if (!response.ok) return { cols: [], rows: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching pitch trend by period:', error);
            return { cols: [], rows: [] };
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
    static async getBatterStats(season, limit = 100, min_pa = 0, teamIds = null) {
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
    static async getPitcherStats(season, limit = 100, min_ip = 0, teamIds = null) {
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
    static async getGames(season, limit = 50) {
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
     * Get KBO team standings (Naver 스포츠 팀 순위)
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
