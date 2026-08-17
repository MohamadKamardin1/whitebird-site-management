export const TANZANIA_TIME_ZONE = "Africa/Dar_es_Salaam";

export function tanzaniaDate(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TANZANIA_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function calendarDate(value: string): Date {
  return new Date(`${value}T12:00:00`);
}
