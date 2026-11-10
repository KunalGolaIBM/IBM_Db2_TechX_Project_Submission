import React, { useState, useEffect } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Navbar } from './components/layout/Navbar';
import { Footer } from './components/layout/Footer';
import { HeroSection } from './components/landing/HeroSection';
import { ProblemSection } from './components/landing/ProblemSection';
import { SolutionSection } from './components/landing/SolutionSection';
import { DifferentiatorsSection } from './components/landing/DifferentiatorsSection';
import { HowItWorksSection } from './components/landing/HowItWorksSection';
import { CtaSection } from './components/landing/CtaSection';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { DashboardPage } from './pages/DashboardPage';
import { Loader2 } from 'lucide-react';

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentRoute, setCurrentRoute] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return window.location.pathname || '/';
    }
    return '/';
  });

  useEffect(() => {
    const handlePopState = () => {
      setCurrentRoute(window.location.pathname || '/');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (route: string) => {
    if (typeof window !== 'undefined') {
      window.history.pushState({}, '', route);
      setCurrentRoute(route);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Route protection rules
  useEffect(() => {
    if (isLoading) return;

    if (currentRoute === '/dashboard' && !isAuthenticated) {
      navigate('/login');
    } else if ((currentRoute === '/login' || currentRoute === '/register') && isAuthenticated) {
      navigate('/dashboard');
    }
  }, [currentRoute, isAuthenticated, isLoading]);

  return (
    <div className="min-h-screen flex flex-col bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100 transition-colors selection:bg-slate-900 selection:text-white dark:selection:bg-white dark:selection:text-slate-950">
      {currentRoute !== '/dashboard' && <Navbar onNavigate={navigate} />}

      <main className="flex-1">
        {isLoading ? (
          <div className="min-h-[50vh] flex flex-col items-center justify-center space-y-3">
            <Loader2 className="w-6 h-6 animate-spin text-slate-400" />
            <span className="text-xs text-slate-400 font-mono">Verifying Db2 Session...</span>
          </div>
        ) : currentRoute === '/login' ? (
          <LoginPage onNavigate={navigate} />
        ) : currentRoute === '/register' ? (
          <RegisterPage onNavigate={navigate} />
        ) : currentRoute === '/dashboard' ? (
          <DashboardPage onNavigate={navigate} />
        ) : (
          <>
            <HeroSection onNavigate={navigate} />
            <ProblemSection />
            <SolutionSection />
            <DifferentiatorsSection />
            <HowItWorksSection />
            <CtaSection onNavigate={navigate} />
          </>
        )}
      </main>

      {currentRoute !== '/dashboard' && <Footer onNavigate={navigate} />}
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ThemeProvider>
  );
};

export default App;
