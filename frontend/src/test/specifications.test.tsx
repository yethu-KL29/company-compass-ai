import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SpecificationEditor } from "../features/products/SpecificationEditor";

it("edits typed specifications using named fields instead of raw JSON", () => {
  const update = vi.fn();
  render(
    <SpecificationEditor value={{ automation_rules: 20 }} onChange={update} />,
  );
  fireEvent.change(screen.getByLabelText("Specification value 1"), {
    target: { value: "50" },
  });
  expect(update).toHaveBeenLastCalledWith({ automation_rules: 50 });
});
