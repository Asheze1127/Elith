import type { AnswerStatus } from "@/types/chat";

interface StatusBadgeProps {
  status: AnswerStatus;
}

const STATUS_LABELS: Record<string, string> = {
  answered: "回答済み",
  needs_review: "確認が必要",
  no_data: "該当資料なし",
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const label = STATUS_LABELS[status] ?? status;
  const statusClass = Object.hasOwn(STATUS_LABELS, status)
    ? `status-badge--${status}`
    : "status-badge--custom";
  return (
    <span className={`status-badge ${statusClass}`} aria-label="回答ステータス">
      {label}
    </span>
  );
}
