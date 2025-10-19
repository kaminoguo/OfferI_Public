/**
 * ChatGPT-style Progress Bar Component
 * Shows smooth animated progress bar with "Working..." text
 *
 * Props:
 * - progress: number (0-100) - progress percentage
 */

interface ProgressBarProps {
  progress: number;
}

export default function ProgressBar({ progress }: ProgressBarProps) {
  // Ensure progress is between 0-100
  const normalizedProgress = Math.min(Math.max(progress, 0), 100);

  return (
    <div className="w-full space-y-2">
      {/* Progress bar */}
      <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 dark:bg-blue-400 transition-all duration-500 ease-out rounded-full"
          style={{ width: `${normalizedProgress}%` }}
        />
      </div>

      {/* "Working..." text */}
      <div className="flex items-center justify-center">
        <span className="text-sm text-gray-600 dark:text-gray-400 font-medium">
          Working...
        </span>
      </div>
    </div>
  );
}
