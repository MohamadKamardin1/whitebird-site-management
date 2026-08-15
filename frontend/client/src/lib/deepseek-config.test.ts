import { describe, expect, it } from "vitest";

describe("DeepSeek configuration", () => {
  it("authenticates the configured server credential against the models endpoint", async () => {
    const apiKey = process.env.DEEPSEEK_API_KEY;
    expect(apiKey, "DEEPSEEK_API_KEY must be configured for this validation").toBeTruthy();

    const response = await fetch("https://api.deepseek.com/models", {
      headers: { Authorization: `Bearer ${apiKey}` },
    });

    expect(response.status).toBe(200);
    const body = (await response.json()) as { object?: string; data?: unknown[] };
    expect(body.object).toBe("list");
    expect(Array.isArray(body.data)).toBe(true);
  }, 30_000);
});

process.on("exit", () => {
  // Keep credentials out of Vitest output and accidental diagnostics.
  delete process.env.DEEPSEEK_API_KEY;
});
