import React from 'react';
import { Link } from 'react-router-dom';
import { Leaf, Twitter, Linkedin, Github } from 'lucide-react';

const Footer = () => {
  return (
    <footer className="bg-dark-900 border-t border-carbon-800/40 pt-16 pb-8 relative z-10">
      <div className="container mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
          
          <div className="col-span-1 md:col-span-2">
            <Link to="/" className="flex items-center gap-2 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-carbon-500 to-emerald-400 flex items-center justify-center">
                <Leaf className="w-5 h-5 text-dark-900" />
              </div>
              <span className="text-xl font-bold tracking-tight text-white">CarbonChain</span>
            </Link>
            <p className="text-gray-400 max-w-sm mb-6">
              The world's first dMRV powered carbon marketplace. Trading absolute integrity globally.
            </p>
            <div className="flex items-center gap-4">
              <a href="#" className="w-10 h-10 rounded-full bg-dark-800 flex items-center justify-center text-gray-400 hover:bg-carbon-900 hover:text-carbon-400 transition-colors">
                <Twitter size={18} />
              </a>
              <a href="#" className="w-10 h-10 rounded-full bg-dark-800 flex items-center justify-center text-gray-400 hover:bg-carbon-900 hover:text-carbon-400 transition-colors">
                <Linkedin size={18} />
              </a>
              <a href="#" className="w-10 h-10 rounded-full bg-dark-800 flex items-center justify-center text-gray-400 hover:bg-carbon-900 hover:text-carbon-400 transition-colors">
                <Github size={18} />
              </a>
            </div>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Platform</h4>
            <ul className="space-y-3">
              <li><Link to="/marketplace" className="text-sm text-gray-400 hover:text-white transition-colors">Marketplace</Link></li>
              <li><Link to="/#tech" className="text-sm text-gray-400 hover:text-white transition-colors">Technology</Link></li>
              <li><Link to="#" className="text-sm text-gray-400 hover:text-white transition-colors">Methodologies</Link></li>
              <li><Link to="#" className="text-sm text-gray-400 hover:text-white transition-colors">Pricing</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="text-white font-semibold mb-4">Company</h4>
            <ul className="space-y-3">
              <li><Link to="#" className="text-sm text-gray-400 hover:text-white transition-colors">About Us</Link></li>
              <li><Link to="#" className="text-sm text-gray-400 hover:text-white transition-colors">Careers</Link></li>
              <li><Link to="#" className="text-sm text-gray-400 hover:text-white transition-colors">Contact</Link></li>
              <li><Link to="#" className="text-sm text-gray-400 hover:text-white transition-colors">Legal</Link></li>
            </ul>
          </div>

        </div>

        <div className="pt-8 border-t border-carbon-800/40 flex flex-col md:flex-row items-center justify-between text-sm text-gray-500">
          <p>© 2026 CarbonChain Labs. All rights reserved.</p>
          <div className="flex gap-4 mt-4 md:mt-0">
            <Link to="#" className="hover:text-white transition-colors">Privacy Policy</Link>
            <Link to="#" className="hover:text-white transition-colors">Terms of Service</Link>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
