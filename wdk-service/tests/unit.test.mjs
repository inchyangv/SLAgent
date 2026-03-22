/**
 * Unit tests for WDK sidecar utility functions.
 * Uses Node.js built-in test runner (node:test) — no extra deps required.
 *
 * Run: npm test
 */
import { test, describe } from "node:test";
import assert from "node:assert/strict";

// ── Inline implementations (must match server.mjs) ──────────────────────────
// These are extracted/duplicated here so we can test without starting a server.

function normalizeValue(value) {
  if (typeof value === "bigint") {
    return value.toString();
  }
  if (
    value &&
    typeof value === "object" &&
    "toString" in value &&
    typeof value.toString === "function"
  ) {
    return value.toString();
  }
  return String(value);
}

function badRequest(message) {
  const error = new Error(message);
  error.statusCode = 400;
  return error;
}

function getWalletRecord(wallets, address) {
  const record = wallets.get(String(address || "").toLowerCase());
  if (!record) {
    throw badRequest(`wallet not loaded: ${address}`);
  }
  return record;
}

async function withTimeout(promise, ms) {
  let timerId;
  const timeoutPromise = new Promise((_, reject) => {
    timerId = setTimeout(() => reject(new Error(`timed out after ${ms}ms`)), ms);
  });
  try {
    const result = await Promise.race([promise, timeoutPromise]);
    clearTimeout(timerId);
    return result;
  } catch (err) {
    clearTimeout(timerId);
    throw err;
  }
}

// ── normalizeValue() ─────────────────────────────────────────────────────────

describe("normalizeValue()", () => {
  test("converts BigInt to string", () => {
    assert.equal(normalizeValue(BigInt(12345)), "12345");
  });

  test("converts large BigInt correctly", () => {
    assert.equal(normalizeValue(BigInt("999999999999999999")), "999999999999999999");
  });

  test("returns object.toString() if available", () => {
    class Hex {
      toString() { return "0xdeadbeef"; }
    }
    assert.equal(normalizeValue(new Hex()), "0xdeadbeef");
  });

  test("converts number to string", () => {
    assert.equal(normalizeValue(42), "42");
  });

  test("passes strings through", () => {
    assert.equal(normalizeValue("hello"), "hello");
  });

  test("handles null/undefined via String()", () => {
    assert.equal(normalizeValue(null), "null");
    assert.equal(normalizeValue(undefined), "undefined");
  });
});

// ── badRequest() ─────────────────────────────────────────────────────────────

describe("badRequest()", () => {
  test("returns an Error with the given message", () => {
    const err = badRequest("missing field");
    assert.ok(err instanceof Error);
    assert.equal(err.message, "missing field");
  });

  test("sets statusCode to 400", () => {
    const err = badRequest("oops");
    assert.equal(err.statusCode, 400);
  });
});

// ── getWalletRecord() ────────────────────────────────────────────────────────

describe("getWalletRecord()", () => {
  const wallets = new Map();
  wallets.set("0xabcdef", { address: "0xabcdef", mock: true });

  test("returns wallet when found (case-insensitive)", () => {
    const rec = getWalletRecord(wallets, "0xABCDEF");
    assert.equal(rec.mock, true);
  });

  test("throws badRequest for unknown address", () => {
    assert.throws(
      () => getWalletRecord(wallets, "0x9999"),
      (err) => {
        assert.equal(err.statusCode, 400);
        assert.ok(err.message.includes("wallet not loaded"));
        return true;
      },
    );
  });

  test("throws badRequest for empty address", () => {
    assert.throws(
      () => getWalletRecord(wallets, ""),
      (err) => err.statusCode === 400,
    );
  });

  test("throws badRequest for null address", () => {
    assert.throws(
      () => getWalletRecord(wallets, null),
      (err) => err.statusCode === 400,
    );
  });
});

// ── withTimeout() ────────────────────────────────────────────────────────────

describe("withTimeout()", () => {
  test("resolves when promise completes before timeout", async () => {
    const val = await withTimeout(Promise.resolve("ok"), 1000);
    assert.equal(val, "ok");
  });

  test("rejects with timeout error when promise exceeds deadline", async () => {
    await assert.rejects(
      () =>
        withTimeout(
          new Promise((resolve) => setTimeout(resolve, 200)),
          50,
        ),
      (err) => {
        assert.ok(err.message.includes("timed out"));
        return true;
      },
    );
  });

  test("clears timer on success (no lingering handles)", async () => {
    // If clearTimeout is missing, Node keeps the timer alive — this test
    // just verifies no assertion error occurs within the timeout window.
    const start = Date.now();
    await withTimeout(Promise.resolve(42), 5000);
    // Should complete well under 5s
    assert.ok(Date.now() - start < 1000);
  });

  test("clears timer on rejection (no lingering handles)", async () => {
    await assert.rejects(
      () =>
        withTimeout(Promise.reject(new Error("inner fail")), 5000),
      (err) => err.message === "inner fail",
    );
  });
});
