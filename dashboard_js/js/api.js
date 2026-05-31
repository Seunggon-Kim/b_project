// API Configuration and Helper Functions
// Nginx Proxy 사용 (/api)
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE_URL = isLocal ? 'http://localhost:8000' : '/api';

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
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
