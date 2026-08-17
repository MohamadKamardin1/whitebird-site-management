import { describe, expect, it } from "vitest";
import { preferredCleanlinessTemplates } from "./cleanlinessTemplates";

describe("preferredCleanlinessTemplates", () => {
  it("shows only official PDF-derived templates when legacy generic templates also exist", () => {
    const templates = [
      { id: 1, description: "Ready-made daily cleanliness survey for operational site review.", is_active: true },
      { id: 2, description: "PDF-derived daily cleanliness worksheet for Toilets / Vyooni.", is_active: true },
      { id: 3, description: "PDF-derived daily cleanliness worksheet for Offices / Ofisini.", is_active: true },
    ];
    expect(preferredCleanlinessTemplates(templates).map((template) => template.id)).toEqual([2, 3]);
  });

  it("keeps active legacy templates available when a site has not yet received official PDF-derived templates", () => {
    const templates = [
      { id: 1, description: "Ready-made daily cleanliness survey for operational site review.", is_active: true },
      { id: 2, description: "Legacy disabled survey", is_active: false },
    ];
    expect(preferredCleanlinessTemplates(templates).map((template) => template.id)).toEqual([1]);
  });
});
