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
};

enum ActionTypes {
  AUTH_START = 'AUTH_START',
  AUTH_SUCCESS = 'AUTH_SUCCESS',
  AUTH_FAIL = 'AUTH_FAIL',
  AUTH_LOGOUT = 'AUTH_LOGOUT',
  CLEAR_ERROR = 'CLEAR_ERROR',
}

type AuthAction =
  | { type: ActionTypes.AUTH_START }
  | { type: ActionTypes.AUTH_SUCCESS; payload: { user: User; token: string } }
  | { type: ActionTypes.AUTH_FAIL; payload: string }
  | { type: ActionTypes.AUTH_LOGOUT }
  | { type: ActionTypes.CLEAR_ERROR };

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
      };
    case ActionTypes.AUTH_FAIL:
      return { ...state, isLoading: false, error: action.payload };
    case ActionTypes.AUTH_LOGOUT:
      return { ...initialState, isLoading: false };
    case ActionTypes.CLEAR_ERROR:
      return { ...state, error: null };
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
        
        // Memastikan response valid tetapi allow null values untuk field opsional
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

        // Jika error adalah 401, logout
        if (error.response?.status === 401) {
          console.log('Unauthorized error, logging out');
          localStorage.removeItem(TOKEN_KEY);
          dispatch({ type: ActionTypes.AUTH_LOGOUT });
        } 
        // Jika error adalah validasi model, try to recover
        else if (error.message?.includes('validation error') || 
                error.response?.data?.detail?.includes('validation error')) {
          console.warn('Validation error during user fetch, trying to login again...');
          // Tampilkan pesan error saja tanpa logout
          dispatch({ 
            type: ActionTypes.AUTH_FAIL, 
            payload: 'Error validasi data user. Silakan coba login ulang.'
          });
        } 
        // Untuk error lainnya, logout
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
      
      // Jika user tidak ada di response, ambil dari endpoint /me
      let user = authResponse.user;
      if (!user) {
        try {
          user = await authService.getCurrentUser();
        } catch (userError: any) {
          console.error('Error fetching user after login:', userError);
          throw new Error('Berhasil login tapi gagal mendapatkan data pengguna');
        }
      }
      
      // Validasi data user
      if (!user || !user.id || !user.username) {
        throw new Error('Data pengguna tidak valid');
      }
      
      dispatch({
        type: ActionTypes.AUTH_SUCCESS,
        payload: { user, token },
      });
    } catch (error: any) {
      console.error('Login error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Email atau password salah';
      dispatch({
        type: ActionTypes.AUTH_FAIL,
        payload: errorMessage,
      });
    }
  };

  const register = async (credentials: RegisterCredentials) => {
    dispatch({ type: ActionTypes.AUTH_START });
    try {
      await authService.register(credentials);
      dispatch({ 
        type: ActionTypes.AUTH_FAIL, 
        payload: "Registrasi berhasil! Silahkan login dengan akun Anda." 
      });
      return Promise.resolve();
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Registrasi gagal. Silakan coba lagi.';
      dispatch({
        type: ActionTypes.AUTH_FAIL,
        payload: errorMessage,
      });
    }
  };

  const logout = () => {
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