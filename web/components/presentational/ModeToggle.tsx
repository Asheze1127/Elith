"use client";

interface ModeToggleProps {
  modes: string[];
  value: string;
  onChange: (mode: string) => void;
}

export function ModeToggle({ modes, value, onChange }: ModeToggleProps) {
  if (modes.length <= 1) return null;

  return (
    <div className="mode-toggle" role="group" aria-label="回答モード">
      {modes.map((mode) => (
        <button
          key={mode}
          className="mode-toggle__button"
          type="button"
          aria-pressed={mode === value}
          onClick={() => onChange(mode)}
        >
          {mode}
        </button>
      ))}
    </div>
  );
}
