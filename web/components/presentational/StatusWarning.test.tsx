// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";
import { WarningList } from "./WarningList";

describe("StatusBadge", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a needs_review badge with a Japanese label", () => {
    render(<StatusBadge status="needs_review" />);

    expect(screen.getByLabelText("回答ステータス").textContent).toBe(
      "確認が必要",
    );
  });

  it("keeps unknown tenant-config statuses visible", () => {
    render(<StatusBadge status="escalate_to_human" />);

    expect(screen.getByLabelText("回答ステータス").textContent).toBe(
      "escalate_to_human",
    );
  });
});

describe("WarningList", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders warning type and message", () => {
    render(
      <WarningList
        warnings={[
          {
            type: "stale_sources",
            message: "古い資料を参照しています。",
          },
        ]}
      />,
    );

    expect(screen.getByLabelText("警告").textContent).toContain("stale_sources");
    expect(screen.getByLabelText("警告").textContent).toContain(
      "古い資料を参照しています。",
    );
  });
});
