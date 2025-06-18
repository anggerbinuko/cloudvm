import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import AuthGuard from './components/guards/AuthGuard';
import MainLayout from './components/layout/MainLayout';
import { Toaster } from 'react-hot-toast';

// Pages
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import CreateVM from './pages/CreateVM';
import QuickDeployVM from './components/vm/QuickDeployVM';
import CustomDeployVM from './components/vm/CustomDeployVM';
import MultiDeployVM from './components/vm/MultiDeployVM';
import CredentialsManagement from './pages/CredentialsManagement';
import DeploymentHistory from './pages/DeploymentHistory';
import VMDetails from './pages/VMDetails';
import NotFound from './pages/NotFound';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <Toaster />
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Protected routes */}
          <Route path="/" element={<AuthGuard><MainLayout /></AuthGuard>}>
            <Route index element={<Dashboard />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="create-vm" element={<CreateVM />} />
            <Route path="create-vm/quick" element={<QuickDeployVM />} />
            <Route path="create-vm/custom" element={<CustomDeployVM />} />
            <Route path="create-vm/multi" element={<MultiDeployVM />} />
            <Route path="quick-deploy-vm" element={<QuickDeployVM />} />
            <Route path="credentials" element={<CredentialsManagement />} />
            <Route path="history" element={<DeploymentHistory />} />
            <Route path="vm/:id" element={<VMDetails />} />
          </Route>
          
          {/* Redirect ke Login untuk root path */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          
          {/* 404 Not Found */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
};

export default App;
