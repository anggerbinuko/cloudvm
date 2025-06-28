// AuthContext.tsx - Fixed Version
import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { AuthState, AuthContextType, LoginCredentials, RegisterCredentials, User } from '../types/auth';
import { TOKEN_KEY } from '../config';
import authService from '../services/authService';

const initialState: AuthState = {
  user: null,
  token: localStorage.getItem(TOKEN_KEY),
  isAuthenticated: false,
  isLoading: true,
  error: null,
  successMessage: null,
};

enum ActionTypes {
  AUTH_START = 'AUTH_START',
  AUTH_SUCCESS = 'AUTH_SUCCESS',
  AUTH_FAIL = 'AUTH_FAIL',
  AUTH_LOGOUT = 'AUTH_LOGOUT',
  CLEAR_ERROR = 'CLEAR_ERROR',
  AUTH_SUCCESS_MESSAGE = 'AUTH_SUCCESS_MESSAGE',
}

type AuthAction =
  | { type: ActionTypes.AUTH_START }
  | { type: ActionTypes.AUTH_SUCCESS; payload: { user: User; token: string } }
  | { type: ActionTypes.AUTH_FAIL; payload: string }
  | { type: ActionTypes.AUTH_LOGOUT }
  | { type: ActionTypes.CLEAR_ERROR }
  | { type: ActionTypes.AUTH_SUCCESS_MESSAGE; payload: string };

const authReducer = (state: AuthState, action: AuthAction): AuthState => {
  switch (action.type) {
    case ActionTypes.AUTH_START:
      return { ...state, isLoading: true, error: null };
    case ActionTypes.AUTH_SUCCESS:
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
        successMessage: null,
      };
    case ActionTypes.AUTH_FAIL:
      return { ...state, isLoading: false, error: action.payload };
    case ActionTypes.AUTH_LOGOUT:
      return { ...initialState, isLoading: false };
    case ActionTypes.CLEAR_ERROR:
      return { ...state, error: null, successMessage: null };
    case ActionTypes.AUTH_SUCCESS_MESSAGE:
      return { ...state, isLoading: false, successMessage: action.payload, error: null };
    default:
      return state;
  }
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    const initAuth = async () => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token) {
        dispatch({ type: ActionTypes.AUTH_LOGOUT });
        return;
      }

      try {
        dispatch({ type: ActionTypes.AUTH_START });
        console.log('Initializing authentication - trying to get current user');
        const user = await authService.getCurrentUser();
        
        console.log('Retrieved user data from API:', user);
        
        if (!user || !user.id || !user.username || !user.email) {
          console.error('Invalid user data structure received:', user);
          throw new Error('Invalid user data received');
        }
        
        dispatch({
          type: ActionTypes.AUTH_SUCCESS,
          payload: { user, token },
        });
      } catch (error: any) {
        console.error('Authentication initialization error:', error);

        if (error.response?.status === 401) {
          console.log('Unauthorized error, logging out');
          localStorage.removeItem(TOKEN_KEY);
          dispatch({ type: ActionTypes.AUTH_LOGOUT });
        } 
        else if (error.message?.includes('validation error') || 
                error.response?.data?.detail?.includes('validation error')) {
          console.warn('Validation error during user fetch, trying to login again...');
          dispatch({ 
            type: ActionTypes.AUTH_FAIL, 
            payload: 'Error validasi data user. Silakan coba login ulang.'
          });
        } 
        else {
          console.error('Unhandled error, logging out', error);
          localStorage.removeItem(TOKEN_KEY);
          dispatch({ type: ActionTypes.AUTH_LOGOUT });
        }
      }
    };

    initAuth();
  }, []);

  const login = async (credentials: LoginCredentials) => {
    dispatch({ type: ActionTypes.AUTH_START });
    try {
      const authResponse = await authService.login(credentials);
      const token = authResponse.token;
      
      // *** FIX 1: Simpan token ke localStorage SEGERA setelah login berhasil ***
      localStorage.setItem(TOKEN_KEY, token);
      
      // Jika user tidak ada di response, ambil dari endpoint /me
      let user = authResponse.user;
      if (!user) {
        try {
          // Sekarang getCurrentUser() bisa menggunakan token yang sudah tersimpan
          user = await authService.getCurrentUser();
        } catch (userError: any) {
          console.error('Error fetching user after login:', userError);
          // Hapus token jika gagal mendapatkan user
          localStorage.removeItem(TOKEN_KEY);
          throw new Error('Berhasil login tapi gagal mendapatkan data pengguna');
        }
      }
      
      // Validasi data user dengan pengecekan yang lebih ketat
      if (!user || !user.id || !user.username) {
        localStorage.removeItem(TOKEN_KEY);
        throw new Error('Data pengguna tidak valid');
      }
      
      // Pastikan semua field yang required ada
      if (typeof user.id !== 'string' && typeof user.id !== 'number') {
        localStorage.removeItem(TOKEN_KEY);
        throw new Error('ID pengguna tidak valid');
      }
      
      if (typeof user.username !== 'string' || user.username.trim() === '') {
        localStorage.removeItem(TOKEN_KEY);
        throw new Error('Username pengguna tidak valid');
      }
      
      // *** FIX 2: Dispatch success dengan sedikit delay untuk memastikan state ter-update ***
      // Pada titik ini user sudah pasti valid
      setTimeout(() => {
        dispatch({
          type: ActionTypes.AUTH_SUCCESS,
          payload: { user: user!, token }, // Non-null assertion karena sudah divalidasi
        });
      }, 100);
      
    } catch (error: any) {
      console.error('Login error:', error);
      localStorage.removeItem(TOKEN_KEY); // Bersihkan token jika ada error
      const errorMessage = error.response?.data?.detail || error.message || 'Email atau password salah';
      dispatch({
        type: ActionTypes.AUTH_FAIL,
        payload: errorMessage,
      });
      throw error; // Re-throw untuk handling di component
    }
  };

  const register = async (credentials: RegisterCredentials) => {
    dispatch({ type: ActionTypes.AUTH_START });
    try {
      await authService.register(credentials);
      dispatch({ 
        type: ActionTypes.AUTH_SUCCESS_MESSAGE, 
        payload: "Registrasi berhasil! Silahkan login dengan akun Anda." 
      });
      return Promise.resolve();
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Registrasi gagal. Silakan coba lagi.';
      dispatch({
        type: ActionTypes.AUTH_FAIL,
        payload: errorMessage,
      });
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY); // Pastikan token dihapus
    authService.logout();
    dispatch({ type: ActionTypes.AUTH_LOGOUT });
  };

  const clearError = () => {
    dispatch({ type: ActionTypes.CLEAR_ERROR });
  };

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        register,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};