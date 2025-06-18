import { createBrowserRouter, Navigate } from 'react-router-dom';
import MainLayout from '../components/layout/MainLayout';
import Dashboard from '../pages/Dashboard';
import CreateVM from '../pages/CreateVM';
import CredentialsManagement from '../pages/CredentialsManagement';
import DeploymentHistory from '../pages/DeploymentHistory';
import Login from '../pages/Login';
import NotFound from '../pages/NotFound';
import AuthGuard from '../components/guards/AuthGuard';

const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />
      },
      {
        path: 'dashboard',
        element: (
          <AuthGuard>
            <Dashboard />
          </AuthGuard>
        ),
      },
      {
        path: 'create-vm',
        element: (
          <AuthGuard>
            <CreateVM />
          </AuthGuard>
        ),
      },
      {
        path: 'credentials',
        element: (
          <AuthGuard>
            <CredentialsManagement />
          </AuthGuard>
        ),
      },
      {
        path: 'history',
        element: (
          <AuthGuard>
            <DeploymentHistory />
          </AuthGuard>
        ),
      },
    ],
  },
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '*',
    element: <NotFound />,
  },
]);

export default router;