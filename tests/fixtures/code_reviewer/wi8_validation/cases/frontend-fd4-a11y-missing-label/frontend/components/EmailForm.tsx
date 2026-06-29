"use client";

/**
 * EmailForm — a form with an unlabeled email input.
 *
 * FD4 violation (WCAG 2.2 AA): the <input type="email"> has no associated
 * <label>, no aria-label, and no aria-labelledby. Screen-reader users cannot
 * determine the input's purpose.
 */
export function EmailForm() {
  return (
    <form>
      <input type="email" placeholder="you@example.com" />
      <button type="submit">Subscribe</button>
    </form>
  );
}
