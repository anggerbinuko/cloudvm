export interface User {
    id: number | string;
    username: string;
    email: string;
    role?: string;
    is_active?: boolean;
    is_admin?: boolean;
    created_at?: string | Date | null;
    updated_at?: string | Date | null;
    hashed_password?: string;
  }
  
  export interface AuthState {
    user: User | null;
    token: string | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    error: string | null;
  }
  
  export interface LoginCredentials {
    username: string;
    password: string;
  }

  export interface RegisterCredentials {
    username: string;
    email: string;
    password: string;
  }
  
  export interface AuthContextType extends AuthState {
    login: (credentials: LoginCredentials) => Promise<void>;
    register: (credentials: RegisterCredentials) => Promise<void>;
    logout: () => void;
    clearError: () => void;
  }