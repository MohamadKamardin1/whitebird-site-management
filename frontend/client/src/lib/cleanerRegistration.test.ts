import { isIndividualCleanerRegistrationReady } from "./cleanerRegistration";
import { describe, expect, it } from "vitest";

describe("isIndividualCleanerRegistrationReady", () => {
  it("requires cleaner identity names, identity number, and birth date before individual HR registration", () => {
    expect(isIndividualCleanerRegistrationReady({ first_name: "Asha", last_name: "Mussa", id_number: "NIDA-01", birth_date: "1996-03-12" })).toBe(true);
    expect(isIndividualCleanerRegistrationReady({ first_name: "Asha", last_name: "", id_number: "NIDA-01", birth_date: "1996-03-12" })).toBe(false);
    expect(isIndividualCleanerRegistrationReady({ first_name: "Asha", last_name: "Mussa", id_number: "   ", birth_date: "1996-03-12" })).toBe(false);
    expect(isIndividualCleanerRegistrationReady({ first_name: "Asha", last_name: "Mussa", id_number: "NIDA-01", birth_date: "" })).toBe(false);
  });
});
