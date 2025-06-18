import React from 'react';
import { useAuth } from '../../contexts/AuthContext';
import Button from '../common/Button';

const Header: React.FC = () => {
  const { user, logout } = useAuth();
  
  return (
    <header className="bg-white border-b border-gray-200 py-4 px-6 flex items-center justify-between">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">VM Management System</h1>
      </div>
      <div className="flex items-center space-x-4">
        <div className="text-sm text-gray-600">
          Welcome, {user?.username}
        </div>
        <Button variant="outline" size="sm" onClick={logout}>
          Logout
        </Button>
      </div>
    </header>
  );
};

export default Header;