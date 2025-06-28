// Login.tsx - Fixed Version
import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Input from '../components/forms/Input';
import Button from '../components/common/Button';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const navigationAttempted = useRef(false); // Flag untuk mencegah multiple navigation

  const {
    login,
    isAuthenticated,
    isLoading,
    error,
    successMessage,
    clearError,
  } = useAuth();

  const navigate = useNavigate();

  useEffect(() => {
    clearError();
  }, [clearError]);

  // *** FIX 3: Improved navigation logic ***
  useEffect(() => {
    if (isAuthenticated && !navigationAttempted.current) {
      navigationAttempted.current = true;
      console.log('User authenticated, navigating to dashboard');
      
      // Tambahkan delay kecil untuk memastikan state sudah ter-update sempurna
      const timer = setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 200);
      
      return () => clearTimeout(timer);
    } else if (!isAuthenticated) {
      navigationAttempted.current = false; // Reset flag jika user logout
    }
  }, [isAuthenticated, navigate]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!email.trim()) {
      newErrors.email = 'Email diperlukan';
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = 'Format email tidak valid';
    }

    if (!password) {
      newErrors.password = 'Password diperlukan';
    } else if (password.length < 6) {
      newErrors.password = 'Password harus minimal 6 karakter';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    try {
      console.log('Attempting login...');
      await login({ username: email, password });
      console.log('Login function completed');
      // Navigation akan di-handle oleh useEffect di atas
    } catch (err) {
      console.error('Login gagal:', err);
      // Error sudah di-handle di AuthContext, tidak perlu action tambahan
    }
  };

  // *** FIX 4: Jika sudah authenticated dan bukan loading, redirect langsung ***
  if (isAuthenticated && !isLoading) {
    console.log('Already authenticated, should redirect');
    // Ini sebagai fallback jika useEffect tidak bekerja
    if (!navigationAttempted.current) {
      navigate('/dashboard', { replace: true });
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-blue-100 rounded-full mix-blend-multiply filter blur-xl opacity-40 animate-blob"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-blue-200 rounded-full mix-blend-multiply filter blur-xl opacity-40 animate-blob animation-delay-2000"></div>
        <div className="absolute top-40 left-40 w-80 h-80 bg-blue-50 rounded-full mix-blend-multiply filter blur-xl opacity-40 animate-blob animation-delay-4000"></div>
      </div>

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 bg-grid-pattern opacity-5"></div>

      <div className="w-full max-w-md relative z-10">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-r from-blue-500 to-blue-600 rounded-2xl shadow-lg mb-4 transform hover:scale-105 transition-transform duration-300">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.002 4.002 0 003 15z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-800 mb-2">CloudDeploy</h1>
          <p className="text-gray-600 text-sm">Otomatisasi Deploy VM AWS & GCP</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl p-8 shadow-xl border border-gray-100">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-2">Selamat Datang Kembali</h2>
            <p className="text-gray-600 text-sm">Masuk untuk mengelola infrastruktur cloud Anda</p>
          </div>

          {/* Alert */}
          {error && (
            <Alert type="error" message={error} />
          )}

          {successMessage && (
            <Alert type="success" message={successMessage} />
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              <Input
                label="Email"
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={errors.email}
                placeholder="admin@cloudcompany.com"
                required
                className="pl-10 bg-gray-50 border-gray-200 text-gray-800 placeholder-gray-500 focus:border-blue-500 focus:ring-blue-500/20"
                icon={
                  <EmailIcon />
                }
              />

              <Input
                label="Password"
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={errors.password}
                placeholder="Masukkan password Anda"
                required
                className="pl-10 bg-gray-50 border-gray-200 text-gray-800 placeholder-gray-500 focus:border-blue-500 focus:ring-blue-500/20"
                icon={
                  <PasswordIcon />
                }
              />
            </div>

            <Button
              type="submit"
              isLoading={isLoading}
              disabled={isLoading}
              className="w-full bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-semibold py-3 px-6 rounded-xl transform hover:scale-105 transition-all duration-200 shadow-lg hover:shadow-xl disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            >
              Masuk ke Dashboard
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-gray-600">
              Belum memiliki akun?{' '}
              <a
                href="/register"
                className="text-blue-600 hover:text-blue-500 transition duration-200 font-medium hover:underline"
              >
                Daftar sekarang
              </a>
            </p>
          </div>
        </div>

        <div className="text-center mt-8">
          <p className="text-gray-500 text-xs">
            © 2024 CloudDeploy. Tugas Akhir 2025.
          </p>
        </div>
      </div>

      <style dangerouslySetInnerHTML={{
        __html: `
          @keyframes blob {
            0% { transform: translate(0px, 0px) scale(1); }
            33% { transform: translate(30px, -50px) scale(1.1); }
            66% { transform: translate(-20px, 20px) scale(0.9); }
            100% { transform: translate(0px, 0px) scale(1); }
          }
          .animate-blob { animation: blob 7s infinite; }
          .animation-delay-2000 { animation-delay: 2s; }
          .animation-delay-4000 { animation-delay: 4s; }
          .bg-grid-pattern {
            background-image: radial-gradient(circle, rgba(255, 255, 255, 0.1) 1px, transparent 1px);
            background-size: 20px 20px;
          }
        `
      }} />
    </div>
  );
};

// Komponen alert reusable
const Alert: React.FC<{ type: 'error' | 'success'; message: string }> = ({ type, message }) => {
  const colors = {
    error: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-700',
      icon: (
        <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
        </svg>
      ),
    },
    success: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-700',
      icon: (
        <svg className="w-5 h-5 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 10a1 1 0 011-1h2a1 1 0 010 2H9a1 1 0 01-1-1z" clipRule="evenodd" />
        </svg>
      ),
    },
  };

  const style = colors[type];

  return (
    <div className={`${style.bg} ${style.border} ${style.text} px-4 py-3 rounded-xl mb-6 flex items-center`} role="alert">
      {style.icon}
      <p className="text-sm">{message}</p>
    </div>
  );
};

// Icon komponen terpisah agar lebih bersih
const EmailIcon = () => (
  <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
  </svg>
);

const PasswordIcon = () => (
  <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
  </svg>
);

export default Login;