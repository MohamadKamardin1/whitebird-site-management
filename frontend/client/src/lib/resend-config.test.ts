import { describe, expect, it } from "vitest";

describe("Resend configuration", () => {
  it("authenticates the configured API key with a read-only domains request", async () => {
    const apiKey = process.env.RESEND_API_KEY;
    expect(apiKey, "RESEND_API_KEY must be supplied for this integration test").toBeTruthy();

    const response = await fetch("https://api.resend.com/domains", {
      headers: { Authorization: `Bearer ${apiKey}` },
    });

    expect(response.ok, `Resend responded with HTTP ${response.status}`).toBe(true);
  }, 15_000);
});
