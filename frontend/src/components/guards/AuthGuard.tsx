import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface AuthGuardProps {
  children?: React.ReactNode;
}

/**
 * Komponen untuk melindungi rute agar hanya bisa diakses oleh pengguna yang sudah login
 * Dapat digunakan dengan dua cara:
 * 1. Sebagai wrapper: <AuthGuard><ProtectedComponent /></AuthGuard>
 * 2. Sebagai elemen di React Router: element={<AuthGuard />}
 */
const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  
  // Tampilkan spinner loading jika masih proses autentikasi
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }
  
  // Redirect ke halaman login jika belum login
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  // Render children jika disediakan, atau Outlet untuk penggunaan dengan Route
  return <>{children ? children : <Outlet />}</>;
};

export default AuthGuard;