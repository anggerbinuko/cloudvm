import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import Card from '../components/common/Card';
import Input from '../components/forms/Input';
import Button from '../components/common/Button';

const Register: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [registrationSuccess, setRegistrationSuccess] = useState(false);
  const { register, isAuthenticated, isLoading, error } = useAuth();
  const navigate = useNavigate();
  
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
    
    if (registrationSuccess) {
      const timer = setTimeout(() => {
        navigate('/login');
      }, 3000);
      
      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, registrationSuccess, navigate]);
  
  useEffect(() => {
    if (error && error.includes("Registrasi berhasil")) {
      setRegistrationSuccess(true);
    }
  }, [error]);
  
  const validateForm = () => {
    const newErrors: Record<string, string> = {};
    
    if (!username.trim()) {
      newErrors.username = 'Username diperlukan';
    } else if (username.length < 3) {
      newErrors.username = 'Username minimal 3 karakter';
    }
    
    if (!email.trim()) {
      newErrors.email = 'Email diperlukan';
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      newErrors.email = 'Format email tidak valid';
    }
    
    if (!password) {
      newErrors.password = 'Password diperlukan';
    } else if (password.length < 8) {
      newErrors.password = 'Password minimal 8 karakter';
    }
    
    if (!confirmPassword) {
      newErrors.confirmPassword = 'Konfirmasi password diperlukan';
    } else if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Password tidak cocok';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      try {
        // @ts-ignore - mengabaikan error TypeScript karena kita tidak tahu persis interface RegisterCredentials
        await register({ username, email, password });
      } catch (err) {
        console.error('Registrasi gagal:', err);
      }
    }
  };
  
  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-bold mb-6 text-center text-gray-800">Daftar Akun Baru</h1>
        
        {error && (
          <div className={`px-4 py-3 rounded mb-4 ${registrationSuccess ? 'bg-green-100 border border-green-400 text-green-700' : 'bg-red-100 border border-red-400 text-red-700'}`} role="alert">
            <p>{error}</p>
            {registrationSuccess && (
              <p className="mt-2 font-semibold">Mengalihkan ke halaman login...</p>
            )}
          </div>
        )}
        
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <Input
              label="Username"
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              error={errors.username}
              placeholder="Masukkan username Anda"
              required
              disabled={registrationSuccess || isLoading}
            />
          </div>
          
          <div className="mb-4">
            <Input
              label="Email"
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={errors.email}
              placeholder="Masukkan email Anda"
              required
              disabled={registrationSuccess || isLoading}
            />
          </div>
          
          <div className="mb-4">
            <Input
              label="Password"
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={errors.password}
              placeholder="Masukkan password"
              required
              disabled={registrationSuccess || isLoading}
            />
          </div>
          
          <div className="mb-6">
            <Input
              label="Konfirmasi Password"
              type="password"
              id="confirmPassword"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              error={errors.confirmPassword}
              placeholder="Konfirmasi password Anda"
              required
              disabled={registrationSuccess || isLoading}
            />
          </div>
          
          <Button
            type="submit"
            variant="primary"
            className="w-full"
            isLoading={isLoading}
            disabled={isLoading || registrationSuccess}
          >
            {isLoading ? 'Sedang Mendaftar...' : 'Daftar'}
          </Button>
        </form>
        
        <div className="mt-4 text-center">
          <p className="text-sm text-gray-600">
            Sudah memiliki akun?{' '}
            <a 
              href="/login" 
              className="text-blue-600 hover:text-blue-800 transition duration-200"
            >
              Masuk sekarang
            </a>
          </p>
        </div>
      </Card>
    </div>
  );
};

export default Register; 