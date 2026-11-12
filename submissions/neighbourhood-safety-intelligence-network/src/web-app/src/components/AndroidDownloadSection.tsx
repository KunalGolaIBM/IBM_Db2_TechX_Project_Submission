import React, { useState, useEffect } from 'react';
import { Smartphone, Download, CheckCircle2, ShieldCheck, QrCode, AlertCircle, Terminal, HelpCircle } from 'lucide-react';

interface AndroidDownloadSectionProps {
  compact?: boolean;
}

export const AndroidDownloadSection: React.FC<AndroidDownloadSectionProps> = ({ compact = false }) => {
  const configuredUrl = import.meta.env.VITE_ANDROID_DOWNLOAD_URL || '/downloads/neighbourhood-safety.apk';
  const appVersion = 'v1.0.0-rc1';
  const releaseDate = 'November 2026';
  
  const [apkAvailable, setApkAvailable] = useState<boolean>(false);
  const [checking, setChecking] = useState<boolean>(true);
  const [showInstructions, setShowInstructions] = useState<boolean>(false);

  useEffect(() => {
    // Check if the configured APK file is actually present in the download directory
    fetch(configuredUrl, { method: 'HEAD' })
      .then((res) => {
        if (res.ok && res.headers.get('content-type')?.includes('application')) {
          setApkAvailable(true);
        } else {
          setApkAvailable(false);
        }
      })
      .catch(() => {
        setApkAvailable(false);
      })
      .finally(() => {
        setChecking(false);
      });
  }, [configuredUrl]);

  return (
    <section id="download-android-app" className={`bg-gradient-to-br from-slate-900 via-slate-850 to-teal-950 text-white rounded-2xl p-8 border border-slate-700 shadow-xl ${compact ? 'my-4' : 'my-12'}`}>
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col md:flex-row items-center justify-between gap-8">
          
          {/* Left Info Column */}
          <div className="flex-1 space-y-4">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-500/20 text-teal-300 border border-teal-500/30 text-xs font-semibold tracking-wide uppercase">
              <Smartphone className="w-3.5 h-3.5" />
              Native Android Companion
            </div>
            
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-teal-600/30 border border-teal-500/50 p-2 flex items-center justify-center shadow-lg shadow-teal-500/10">
                <ShieldCheck className="w-10 h-10 text-teal-400" />
              </div>
              <div>
                <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
                  Get the Neighbourhood Safety Android App
                </h2>
                <p className="text-slate-300 text-sm mt-1">
                  Full-stack synchronized civic protection for residents, guardians, and verified responders on the go.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2 text-xs text-slate-300">
              <div className="bg-slate-800/80 p-2.5 rounded-lg border border-slate-700">
                <span className="text-slate-400 block">Version</span>
                <span className="font-semibold text-white">{appVersion}</span>
              </div>
              <div className="bg-slate-800/80 p-2.5 rounded-lg border border-slate-700">
                <span className="text-slate-400 block">Release Date</span>
                <span className="font-semibold text-white">{releaseDate}</span>
              </div>
              <div className="bg-slate-800/80 p-2.5 rounded-lg border border-slate-700 col-span-2 sm:col-span-1">
                <span className="text-slate-400 block">Architecture</span>
                <span className="font-semibold text-white">Jetpack Compose / M3</span>
              </div>
            </div>

            {/* Actions & Status */}
            <div className="pt-2 flex flex-wrap items-center gap-4">
              {apkAvailable ? (
                <a
                  href={configuredUrl}
                  download="neighbourhood-safety.apk"
                  className="inline-flex items-center gap-2.5 bg-teal-500 hover:bg-teal-400 text-slate-950 font-semibold px-6 py-3 rounded-xl shadow-lg shadow-teal-500/25 transition-all hover:scale-[1.02] active:scale-[0.98]"
                >
                  <Download className="w-5 h-5" />
                  Download APK (Direct)
                </a>
              ) : (
                <div className="inline-flex items-center gap-2.5 bg-slate-800 border border-amber-500/40 text-amber-300 text-sm font-medium px-5 py-3 rounded-xl">
                  <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>Build ready in source — generate APK with Gradle</span>
                </div>
              )}

              <button
                onClick={() => setShowInstructions(!showInstructions)}
                className="inline-flex items-center gap-2 text-slate-300 hover:text-white text-sm bg-slate-800/60 hover:bg-slate-800 px-4 py-3 rounded-xl border border-slate-700 transition"
              >
                <HelpCircle className="w-4 h-4 text-teal-400" />
                {showInstructions ? 'Hide Instructions' : 'Installation Guide'}
              </button>
            </div>
          </div>

          {/* Right Column: QR Code & Verification Card */}
          <div className="w-full md:w-64 bg-slate-800/90 border border-slate-700 rounded-2xl p-5 text-center flex flex-col items-center">
            <div className="bg-white p-3 rounded-xl shadow-md mb-3">
              {/* Clean SVG Mock QR Code */}
              <svg className="w-32 h-32" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="100" height="100" fill="white" />
                {/* Corner markers */}
                <rect x="10" y="10" width="24" height="24" fill="#0F172A" />
                <rect x="14" y="14" width="16" height="16" fill="white" />
                <rect x="18" y="18" width="8" height="8" fill="#0D9488" />

                <rect x="66" y="10" width="24" height="24" fill="#0F172A" />
                <rect x="70" y="14" width="16" height="16" fill="white" />
                <rect x="74" y="18" width="8" height="8" fill="#0D9488" />

                <rect x="10" y="66" width="24" height="24" fill="#0F172A" />
                <rect x="14" y="70" width="16" height="16" fill="white" />
                <rect x="18" y="74" width="8" height="8" fill="#0D9488" />

                {/* Pattern Data Points */}
                <rect x="42" y="14" width="6" height="6" fill="#0F172A" />
                <rect x="52" y="24" width="6" height="6" fill="#0F172A" />
                <rect x="42" y="34" width="6" height="6" fill="#0D9488" />
                <rect x="52" y="44" width="6" height="6" fill="#0F172A" />
                <rect x="22" y="44" width="6" height="6" fill="#0F172A" />
                <rect x="34" y="52" width="6" height="6" fill="#0F172A" />
                <rect x="66" y="44" width="6" height="6" fill="#0D9488" />
                <rect x="76" y="54" width="6" height="6" fill="#0F172A" />
                <rect x="44" y="66" width="6" height="6" fill="#0F172A" />
                <rect x="54" y="76" width="6" height="6" fill="#0D9488" />
                <rect x="66" y="76" width="6" height="6" fill="#0F172A" />
                <rect x="78" y="66" width="6" height="6" fill="#0F172A" />
              </svg>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-slate-300">
              <QrCode className="w-3.5 h-3.5 text-teal-400" />
              Scan with Android Camera
            </div>
            <span className="text-[11px] text-slate-400 mt-1">Direct device download link</span>
          </div>

        </div>

        {/* Collapsible Installation Instructions */}
        {showInstructions && (
          <div className="mt-6 pt-6 border-t border-slate-700/80 grid md:grid-cols-2 gap-4 text-xs text-slate-300 animate-fadeIn">
            <div className="space-y-2 bg-slate-800/50 p-4 rounded-xl border border-slate-700">
              <h3 className="font-semibold text-white flex items-center gap-1.5 text-sm">
                <CheckCircle2 className="w-4 h-4 text-teal-400" />
                Installing APK on Physical Android Device
              </h3>
              <ol className="list-decimal list-inside space-y-1.5 text-slate-300">
                <li>Download the APK file to your Android phone or transfer via USB.</li>
                <li>Tap the downloaded <code className="text-teal-300 bg-slate-900 px-1 py-0.5 rounded">.apk</code> file in your Notifications or Files app.</li>
                <li>When prompted, enable <strong>"Install unknown apps"</strong> for your browser/file manager.</li>
                <li>Tap <strong>Install</strong>. Launch <strong>Neighbourhood Safety</strong>.</li>
                <li>In App Settings, set the API Base URL to your backend computer's LAN IP (e.g., <code className="text-teal-300 bg-slate-900 px-1 py-0.5 rounded">http://192.168.1.X:8000</code>).</li>
              </ol>
            </div>

            <div className="space-y-2 bg-slate-800/50 p-4 rounded-xl border border-slate-700">
              <h3 className="font-semibold text-white flex items-center gap-1.5 text-sm">
                <Terminal className="w-4 h-4 text-teal-400" />
                Building via Gradle / Android Studio
              </h3>
              <p className="text-slate-300">
                To build the debug or signed release APK directly from the source repository:
              </p>
              <pre className="bg-slate-950 p-2.5 rounded-lg text-teal-300 overflow-x-auto text-[11px] font-mono border border-slate-800">
# Build Debug APK
gradle :app:assembleDebug

# Output location:
app/build/outputs/apk/debug/app-debug.apk
              </pre>
              <p className="text-slate-400 text-[11px]">
                Emulator default host address: <code className="text-teal-300">http://10.0.2.2:8000</code>
              </p>
            </div>
          </div>
        )}

      </div>
    </section>
  );
};
