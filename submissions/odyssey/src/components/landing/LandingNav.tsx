import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import ThemeToggle from '../ThemeToggle';

export default function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const scrollToSection = (id: string) => {
    setMobileOpen(false);
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <header
      id="landing-nav"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled
          ? 'border-b'
          : ''
      }`}
      style={{
        background: scrolled
          ? 'rgba(5, 8, 23, 0.88)'
          : 'transparent',
        backdropFilter: scrolled ? 'blur(20px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(20px)' : 'none',
        borderColor: scrolled ? 'rgba(49, 75, 115, 0.3)' : 'transparent',
      }}
    >
      <div className="max-w-7xl mx-auto px-5 sm:px-8 lg:px-10">
        <div className="flex justify-between items-center h-16 md:h-[72px]">

          {/* Logo */}
          <Link
            to="/"
            className="text-base font-semibold tracking-[0.3em] font-display transition-all duration-300"
            style={{ color: 'var(--color-ody-gold)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-ody-ink)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-ody-gold)')}
          >
            ODYSSEY
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
            <button
              onClick={() => scrollToSection('how-it-works')}
              className="px-4 py-2 text-[0.8125rem] font-medium tracking-wide transition-colors duration-200 cursor-pointer bg-transparent border-none"
              style={{ color: 'var(--color-ody-ink-muted)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-ody-ink)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-ody-ink-muted)')}
            >
              How it works
            </button>
            <Link
              to="/auth"
              className="px-4 py-2 text-[0.8125rem] font-medium tracking-wide transition-colors duration-200"
              style={{ color: 'var(--color-ody-ink-muted)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-ody-ink)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-ody-ink-muted)')}
            >
              Sign in
            </Link>

            {/* Primary CTA */}
            <Link
              to="/auth"
              className="ml-3 px-5 py-2.5 text-[0.8125rem] font-semibold tracking-wide rounded-lg active:scale-[0.97] transition-all duration-200 inline-flex items-center border"
              style={{
                background: 'linear-gradient(135deg, var(--color-ody-copper) 0%, var(--color-ody-gold) 100%)',
                color: '#050817',
                borderColor: 'transparent',
                boxShadow: '0 2px 16px -2px rgba(229, 183, 106, 0.3)',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 4px 24px -4px rgba(229, 183, 106, 0.5)';
                (e.currentTarget as HTMLAnchorElement).style.filter = 'brightness(1.08)';
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLAnchorElement).style.boxShadow = '0 2px 16px -2px rgba(229, 183, 106, 0.3)';
                (e.currentTarget as HTMLAnchorElement).style.filter = 'brightness(1)';
              }}
            >
              Try Odyssey
            </Link>
            <ThemeToggle />
          </nav>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden relative w-8 h-8 flex items-center justify-center cursor-pointer bg-transparent border-none"
            aria-label="Toggle menu"
          >
            <span
              className={`block absolute h-[1.5px] w-5 transition-all duration-300 ${
                mobileOpen ? 'rotate-45 translate-y-0' : '-translate-y-1.5'
              }`}
              style={{ backgroundColor: 'var(--color-ody-ink)' }}
            />
            <span
              className={`block absolute h-[1.5px] w-5 transition-all duration-300 ${
                mobileOpen ? 'opacity-0' : 'opacity-100'
              }`}
              style={{ backgroundColor: 'var(--color-ody-ink)' }}
            />
            <span
              className={`block absolute h-[1.5px] w-5 transition-all duration-300 ${
                mobileOpen ? '-rotate-45 translate-y-0' : 'translate-y-1.5'
              }`}
              style={{ backgroundColor: 'var(--color-ody-ink)' }}
            />
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <div
        className={`md:hidden overflow-hidden transition-all duration-400 ${
          mobileOpen ? 'max-h-72 opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div
          className="px-5 pb-6 pt-2 border-t"
          style={{
            background: 'rgba(5, 8, 23, 0.96)',
            backdropFilter: 'blur(20px)',
            borderColor: 'rgba(49, 75, 115, 0.3)',
          }}
        >
          <button
            onClick={() => scrollToSection('how-it-works')}
            className="block w-full text-left py-3 text-sm font-medium transition-colors cursor-pointer bg-transparent border-none"
            style={{ color: 'var(--color-ody-ink-muted)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-ody-ink)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-ody-ink-muted)')}
          >
            How it works
          </button>
          <Link
            to="/auth"
            className="block py-3 text-sm font-medium transition-colors"
            style={{ color: 'var(--color-ody-ink-muted)' }}
          >
            Sign in
          </Link>
          <Link
            to="/auth"
            onClick={() => setMobileOpen(false)}
            className="mt-3 block text-center w-full px-5 py-3 text-sm font-semibold tracking-wide rounded-lg transition-all duration-200 border-none"
            style={{
              background: 'linear-gradient(135deg, var(--color-ody-copper) 0%, var(--color-ody-gold) 100%)',
              color: '#050817',
              boxShadow: '0 2px 16px -2px rgba(229, 183, 106, 0.3)',
            }}
          >
            Try Odyssey
          </Link>
          <div className="mt-4 flex justify-end">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </header>
  );
}
