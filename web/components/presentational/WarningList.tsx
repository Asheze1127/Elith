import type { Warning } from "@/types/chat";

interface WarningListProps {
  warnings: Warning[];
}

export function WarningList({ warnings }: WarningListProps) {
  if (warnings.length === 0) return null;

  return (
    <section className="warning-list" aria-label="警告">
      <ul>
        {warnings.map((warning, index) => (
          <li key={`${warning.type}-${index}`}>
            <span className="warning-list__type">{warning.type}</span>
            <span>{warning.message}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
