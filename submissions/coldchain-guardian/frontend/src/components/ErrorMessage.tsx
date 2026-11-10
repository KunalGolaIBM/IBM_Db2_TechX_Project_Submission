interface Props { message: string; onRetry?: () => void; }
export default function ErrorMessage({ message, onRetry }: Props) {
  return (
    <div className="rounded-lg bg-red-900/20 border border-red-700/50 p-6 text-center">
      <p className="text-red-400 font-medium mb-2">Error</p>
      <p className="text-slate-400 text-sm mb-4">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}
