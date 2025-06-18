import http from './httpService';
import { LoginCredentials, RegisterCredentials, User } from '../types/auth';
import { TOKEN_KEY } from '../config';

// Interface untuk response dari backend
interface BackendAuthResponse {
  access_token: string;
  token_type: string;
  user?: User;
}

// Interface yang digunakan di frontend
interface AuthResponse {
  user?: User;
  token: string;
  token_type: string;
}

const authService = {
  login: async (credentials: LoginCredentials): Promise<AuthResponse> => {
    try {
      // Gunakan endpoint login-json yang menerima body JSON
      const response = await http.post<BackendAuthResponse>('/api/v1/auth/login-json', {
        username: credentials.username,
        password: credentials.password
      });
      
      // Ubah format response agar sesuai dengan yang diharapkan
      const { user, access_token, token_type } = response.data;
      
      // Simpan token ke local storage
      localStorage.setItem(TOKEN_KEY, access_token);
      
      return {
        user,
        token: access_token,
        token_type
      };
    } catch (error: any) {
      console.error('Error pada request login:', error.response?.data || error.message);
      throw error;
    }
  },
  
  getCurrentUser: async (): Promise<User> => {
    try {
      console.log('Getting current user...');
      const response = await http.get<any>('/api/v1/users/me');
      
      console.log('Current user response:', response.data);
      
      // Konversi datetime menjadi string untuk menghindari masalah validasi
      const userData: User = {
        id: response.data.id,
        username: response.data.username,
        email: response.data.email,
        is_active: response.data.is_active ?? true,
        is_admin: response.data.is_admin ?? false,
        // Pastikan format tanggal yang benar
        created_at: response.data.created_at,
        updated_at: response.data.updated_at || null
      };
      
      console.log('Transformed user data:', userData);
      
      return userData;
    } catch (error: any) {
      console.error('Error getting current user:', error.response?.data || error.message);
      throw error;
    }
  },
  
  register: async (userData: RegisterCredentials): Promise<AuthResponse> => {
    try {
      // Pastikan data dikirim sebagai JSON, bukan FormData
      const response = await http.post<BackendAuthResponse>('/api/v1/auth/register', {
        username: userData.username,
        email: userData.email,
        password: userData.password
      });
      
      // Simpan token ke local storage
      localStorage.setItem(TOKEN_KEY, response.data.access_token);
      
      // Sesuaikan response seperti login
      return {
        user: response.data.user,
        token: response.data.access_token,
        token_type: response.data.token_type
      };
    } catch (error) {
      console.error('Error registering user:', error);
      throw error;
    }
  },
  
  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = '/login';
  }
};

export default authService;