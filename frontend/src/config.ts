// Konfigurasi global aplikasi
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Log konfigurasi API untuk debugging
console.log('API Base URL:', API_BASE_URL);

// Key untuk token JWT di localStorage
export const TOKEN_KEY = 'auth_token';

// Ekspor default API_BASE_URL
export default API_BASE_URL; 