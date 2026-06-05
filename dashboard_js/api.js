// API Configuration and Helper Functions
const API_BASE_URL = '/api';

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
     * Get batter statistics
     */
    static async getBatterStats(season = 2025, limit = 100, teamId = null, minPA = null) {
        try {
            let url = `${API_BASE_URL}/stats/batters?season=${season}&limit=${limit}`;
            if (teamId) url += `&team_id=${encodeURIComponent(teamId)}`;
            if (minPA) url += `&min_pa=${minPA}`;

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
     */
    static async getPitcherStats(season = 2025, limit = 100, teamId = null, minIP = null) {
        try {
            let url = `${API_BASE_URL}/stats/pitchers?season=${season}&limit=${limit}`;
            if (teamId) url += `&team_id=${encodeURIComponent(teamId)}`;
            if (minIP) url += `&min_ip=${minIP}`;

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
     * Get player arsenal (pitch locations)
     */
    static async getPitchArsenal(playerId) {
        try {
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/arsenal?t=${Date.now()}`);
            if (!response.ok) throw new Error('Failed to fetch player arsenal');
            return await response.json();
        } catch (error) {
            console.error('Error fetching player arsenal:', error);
            return { arsenal: [] };
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
