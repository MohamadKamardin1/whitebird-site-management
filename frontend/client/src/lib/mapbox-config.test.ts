import { describe, expect, it } from "vitest";

describe("Mapbox configuration", () => {
  it("authenticates against the Mapbox style endpoint", async () => {
    const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || process.env.VITE_MAPBOX_ACCESS_TOKEN;
    expect(token, "VITE_MAPBOX_ACCESS_TOKEN must be configured").toBeTruthy();
    const response = await fetch(`https://api.mapbox.com/styles/v1/mapbox/streets-v12?access_token=${encodeURIComponent(token as string)}`);
    expect(response.ok).toBe(true);
    const payload = (await response.json()) as { version?: number; name?: string };
    expect(payload.version).toBeGreaterThan(0);
    expect(payload.name).toBeTruthy();
  }, 15_000);
});
