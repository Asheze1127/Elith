// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ModeToggle } from "./ModeToggle";

describe("ModeToggle", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a segmented control and emits the selected mode", () => {
    const onChange = vi.fn();

    render(
      <ModeToggle
        modes={["internal", "external"]}
        value="internal"
        onChange={onChange}
      />,
    );

    expect(screen.getByRole("group", { name: "回答モード" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "internal" }).getAttribute("aria-pressed")).toBe(
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: "external" }));

    expect(onChange).toHaveBeenCalledWith("external");
  });
});
