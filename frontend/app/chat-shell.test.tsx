/**
 * Chat shell smoke + a11y tests (S3.8.1).
 *
 * Uses SSR (renderToStaticMarkup) + JSDOM for structural assertions.
 * The ChatShell is a "use client" component but we can still SSR its
 * initial render to verify the empty state, header, composer presence,
 * and ARIA landmarks. Failure paths first (FD6).
 */

import { describe, expect, it } from "vitest";
import { JSDOM } from "jsdom";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ChatShell } from "./chat-shell";

function dom(html: string): Document {
  return new JSDOM(`<!doctype html><html><body>${html}</body></html>`).window
    .document;
}

function render(email = "test@example.com"): Document {
  const html = renderToStaticMarkup(
    React.createElement(ChatShell, { userEmail: email }),
  );
  return dom(html);
}

describe("ChatShell — failure / edge-case paths first", () => {
  it("renders empty-state prompt when no messages exist", () => {
    const d = render();
    const text = d.body.textContent ?? "";
    expect(text).toContain("What can I help you with?");
  });

  it("does NOT render any message bubbles in initial state", () => {
    const d = render();
    const articles = d.querySelectorAll("article");
    expect(articles.length).toBe(0);
  });
});

describe("ChatShell — header rendering", () => {
  it("displays the user email in the header", () => {
    const d = render("rajnish@test.com");
    const header = d.querySelector("header");
    expect(header?.textContent).toContain("rajnish@test.com");
  });

  it("displays the app name in the header", () => {
    const d = render();
    const header = d.querySelector("header");
    expect(header?.textContent).toContain("ReAct Agent");
  });

  it("includes a sign-out link", () => {
    const d = render();
    const signOutLink = d.querySelector('a[href="/api/auth/sign-out"]');
    expect(signOutLink).toBeTruthy();
    expect(signOutLink?.textContent).toContain("Sign out");
  });
});

describe("ChatShell — composer presence", () => {
  it("renders the composer form", () => {
    const d = render();
    const form = d.querySelector("form");
    expect(form).toBeTruthy();
  });

  it("renders a textarea with 'Compose message' aria-label", () => {
    const d = render();
    const ta = d.querySelector('textarea[aria-label="Compose message"]');
    expect(ta).toBeTruthy();
  });

  it("renders a Send button that is initially disabled", () => {
    const d = render();
    const btn = d.querySelector('button[aria-label="Send"]');
    expect(btn).toBeTruthy();
    expect(btn?.hasAttribute("disabled")).toBe(true);
  });
});

describe("ChatShell — layout structure", () => {
  it("uses a grid layout with header, main, and composer", () => {
    const d = render();
    const root = d.querySelector("div");
    expect(root?.className).toContain("grid");
    expect(root?.className).toContain("grid-rows");
  });

  it("has a <main> element for the messages area", () => {
    const main = render().querySelector("main");
    expect(main).toBeTruthy();
  });
});
