/**
 * desktop_auth_state pure-helper tests (P5 Step 2). Failure/guard paths first
 * (FD6): malformed desktop params must be rejected so a bad request can never
 * fall through to a weaker flow.
 */

import { describe, expect, it } from "vitest";
import {
  DESKTOP_REDIRECT_URI,
  isDesktopClient,
  parseDesktopSignIn,
  parseDesktopCallback,
  DESKTOP_POST_AUTH_PATH,
} from "./desktop_auth_state";

const sp = (q: string) => new URLSearchParams(q);
// A valid 43-char base64url S256 challenge/verifier sample.
const VALID_B64URL = "abcdefghijklmnopqrstuvwxyz0123456789-_ABCDEF";

describe("isDesktopClient", () => {
  it("is true only for client=desktop", () => {
    expect(isDesktopClient(sp("client=desktop"))).toBe(true);
    expect(isDesktopClient(sp("client=web"))).toBe(false);
    expect(isDesktopClient(sp(""))).toBe(false);
  });
});

describe("parseDesktopSignIn — guard paths first", () => {
  it("rejects when code_challenge is missing", () => {
    expect(parseDesktopSignIn(sp("state=abcdefghij"))).toBeNull();
  });

  it("rejects when state is missing", () => {
    expect(parseDesktopSignIn(sp(`code_challenge=${VALID_B64URL}`))).toBeNull();
  });

  it("rejects a too-short challenge", () => {
    expect(parseDesktopSignIn(sp(`code_challenge=short&state=abcdefghij`))).toBeNull();
  });

  it("rejects a non-base64url challenge", () => {
    const bad = "a".repeat(20) + "!!!" + "a".repeat(20);
    expect(parseDesktopSignIn(sp(`code_challenge=${bad}&state=abcdefghij`))).toBeNull();
  });

  it("rejects a too-short state nonce", () => {
    expect(parseDesktopSignIn(sp(`code_challenge=${VALID_B64URL}&state=short`))).toBeNull();
  });

  it("accepts a well-formed challenge + state", () => {
    const got = parseDesktopSignIn(sp(`code_challenge=${VALID_B64URL}&state=abcdefghij`));
    expect(got).toEqual({ codeChallenge: VALID_B64URL, state: "abcdefghij" });
  });
});

describe("parseDesktopCallback — guard paths first", () => {
  it("rejects when code is missing", () => {
    expect(parseDesktopCallback(sp(`code_verifier=${VALID_B64URL}&state=abcdefghij`))).toBeNull();
  });

  it("rejects when code_verifier is missing", () => {
    expect(parseDesktopCallback(sp("code=xyz&state=abcdefghij"))).toBeNull();
  });

  it("rejects when state is missing", () => {
    expect(parseDesktopCallback(sp(`code=xyz&code_verifier=${VALID_B64URL}`))).toBeNull();
  });

  it("rejects a too-short verifier", () => {
    expect(parseDesktopCallback(sp("code=xyz&code_verifier=short&state=abcdefghij"))).toBeNull();
  });

  it("rejects a non-base64url verifier", () => {
    const bad = "a".repeat(20) + "###" + "a".repeat(20);
    expect(parseDesktopCallback(sp(`code=xyz&code_verifier=${bad}&state=abcdefghij`))).toBeNull();
  });

  it("accepts well-formed code + verifier + state", () => {
    const got = parseDesktopCallback(
      sp(`code=xyz&code_verifier=${VALID_B64URL}&state=abcdefghij`),
    );
    expect(got).toEqual({ code: "xyz", codeVerifier: VALID_B64URL, state: "abcdefghij" });
  });
});

describe("constants", () => {
  it("defaults the desktop redirect to the registered custom scheme", () => {
    // The env override may set this in some environments; assert the shape.
    expect(DESKTOP_REDIRECT_URI).toMatch(/:\/\/auth\/callback$/);
  });

  it("post-auth path is a same-origin relative root", () => {
    expect(DESKTOP_POST_AUTH_PATH).toBe("/");
  });
});
