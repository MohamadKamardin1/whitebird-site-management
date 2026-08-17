import { describe, expect, it } from "vitest";
import { aggregateDailyAttendance } from "./attendanceSummary";

describe("aggregateDailyAttendance", () => {
  it("uses live outcomes and counts scheduled rows without treating half-present or absent cleaners as fully present", () => {
    expect(aggregateDailyAttendance([
      { status: "present", attendance_outcome: "present" },
      { status: "late", attendance_outcome: "present" },
      { status: "present", attendance_outcome: "half_present" },
      { status: "absent", attendance_outcome: "absent" },
    ])).toEqual({ total: 4, present: 2 });
  });
});
