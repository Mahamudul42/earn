import { describe, expect, it } from "vitest";
import { cn } from "./cn";

describe("cn", () => {
  it("joins truthy class names", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("drops falsy values and merges conditionals", () => {
    expect(cn("a", false && "b", null, undefined, "c")).toBe("a c");
    expect(cn("base", { active: true, hidden: false })).toBe("base active");
  });
});
