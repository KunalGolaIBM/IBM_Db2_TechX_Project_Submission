"use client";

interface ProviderLogoProps {
  src?: string;
  alt: string;
  fallback: string;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: { container: "w-8 h-8 rounded-lg", img: "w-5 h-5", text: "text-xs" },
  md: { container: "w-10 h-10 rounded-xl", img: "w-6 h-6", text: "text-sm" },
  lg: { container: "w-16 h-16 rounded-2xl", img: "w-10 h-10", text: "text-2xl" },
};

export function ProviderLogo({ src, alt, fallback, size = "md" }: ProviderLogoProps) {
  const s = sizeMap[size];
  return (
    <div className={`${s.container} bg-gray-100 dark:bg-gray-800 flex items-center justify-center overflow-hidden shrink-0 border border-border dark:border-dark-border`}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={alt}
          className={`${s.img} object-contain`}
          onError={(e) => {
            const target = e.target as HTMLImageElement;
            target.style.display = "none";
            const parent = target.parentElement;
            if (parent) {
              parent.innerHTML = `<span class="font-bold ${s.text} text-gray-500">${fallback[0]}</span>`;
            }
          }}
        />
      ) : (
        <span className={`font-bold ${s.text} text-gray-500`}>{fallback[0]}</span>
      )}
    </div>
  );
}
