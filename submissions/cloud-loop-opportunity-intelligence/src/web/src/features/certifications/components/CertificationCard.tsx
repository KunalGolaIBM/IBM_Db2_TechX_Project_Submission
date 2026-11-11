"use client";

import { Star, Users, ExternalLink } from "lucide-react";
import { ProviderLogo } from "@/components/ui/ProviderLogo";
import { StatusSelector } from "@/components/ui/StatusSelector";
import { cn } from "@/lib/utils";
import { Certification } from "../types/Certification";

export function CertificationCard({ cert }: { cert: Certification }) {
  const getGradient = (id: string) => {
    const gradients = [
      "from-blue-600 to-indigo-900",
      "from-teal-500 to-emerald-800",
      "from-purple-600 to-indigo-950",
      "from-rose-500 to-red-800",
      "from-cyan-500 to-blue-800",
      "from-orange-500 to-amber-800",
      "from-indigo-600 to-purple-900"
    ];
    let sum = 0;
    for (let i = 0; i < id.length; i++) sum += id.charCodeAt(i);
    return gradients[sum % gradients.length];
  };

  return (
    <a 
      href={cert.enrollUrl} 
      target="_blank" 
      rel="noopener noreferrer" 
      className="block h-full group"
    >
      <div className="card-base p-0 h-full flex flex-col overflow-hidden transition-all duration-300 hover:shadow-xl hover:shadow-primary/5 hover:-translate-y-1">
        {/* Thumbnail */}
        <div className={cn(
          "w-full h-40 bg-gradient-to-br flex flex-col justify-between p-4 relative overflow-hidden shrink-0",
          getGradient(cert.id)
        )}>
          {/* Subtle overlay pattern */}
          <div className="absolute inset-0 bg-black/10 mix-blend-overlay" />
          <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:16px_16px]" />

          {/* Badge */}
          <div className="z-10 self-start">
            <span className="text-[10px] font-black tracking-wider uppercase px-2.5 py-1 rounded-full bg-emerald-500 text-white shadow-md border border-emerald-400/20">
              {cert.badge}
            </span>
          </div>

          {/* Icon overlay */}
          <div className="z-10">
            <div className="w-8 h-8 rounded-lg bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 mb-2">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-5 flex-1 flex flex-col gap-3 justify-between">
          <div className="space-y-2">
            {/* Provider */}
            <div className="flex items-center gap-2">
              <ProviderLogo
                src={cert.providerLogo}
                alt={cert.provider}
                fallback={cert.provider}
                size="sm"
              />
              <p className="text-xs font-semibold text-text-secondary dark:text-dark-text-secondary">
                {cert.provider}
              </p>
            </div>

            {/* Title */}
            <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary leading-snug group-hover:text-primary transition-colors line-clamp-2">
              {cert.name}
            </h3>

            {/* Description */}
            <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed line-clamp-2">
              {cert.description}
            </p>
          </div>

          <div className="space-y-3 pt-2">
            {/* Interested Count */}
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1 text-text-secondary dark:text-dark-text-secondary font-medium">
                <Users size={12} className="text-primary" />
                {cert.interestedCount}
              </span>
              <span className="flex items-center gap-1 text-amber-500 font-medium">
                <Star size={12} className="fill-amber-500" />
                4.9
              </span>
            </div>

            {/* CTA Button */}
            <div className="flex items-center justify-between pt-2 border-t border-border dark:border-dark-border gap-3">
              <span className="inline-flex items-center gap-1 text-xs font-bold text-primary group-hover:underline">
                Enroll Now <ExternalLink size={12} />
              </span>
              <StatusSelector id={cert.id} />
            </div>
          </div>
        </div>
      </div>
    </a>
  );
}
