import { describe, expect, it } from "vitest";
import { tanzaniaDate } from "./dates";

describe("tanzaniaDate", () => {
  it("uses the Tanzania calendar day instead of UTC when the two days differ", () => {
    expect(tanzaniaDate(new Date("2026-08-17T21:30:00.000Z"))).toBe("2026-08-18");
    expect(tanzaniaDate(new Date("2026-08-17T19:30:00.000Z"))).toBe("2026-08-17");
  });
});
