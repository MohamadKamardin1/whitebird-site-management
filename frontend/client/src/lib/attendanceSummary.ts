export type AttendanceSummaryRecord = {
  status?: string | null;
  attendance_outcome?: string | null;
};

export function aggregateDailyAttendance(records: AttendanceSummaryRecord[]) {
  return {
    total: records.length,
    present: records.filter((record) => {
      const value = record.attendance_outcome || record.status || "";
      return value === "present" || value === "late";
    }).length,
  };
}
