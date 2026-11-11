import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background flex items-center justify-center px-4 py-24">
      <div className="w-full max-w-md">
        <SignIn
          appearance={{
            elements: {
              formButtonPrimary: "bg-secondary hover:bg-secondary/90 text-white transition-colors",
              card: "shadow-card border border-border dark:border-dark-border dark:bg-dark-card",
            },
          }}
        />
      </div>
    </div>
  );
}
