"use client";

import { useState } from "react";

/**
 * ContactForm — an accessible form.
 *
 * FD4 clean: the input has an associated <label htmlFor> (WCAG 2.2 AA).
 * No cloud calls, no secrets in the bundle.
 */
export function ContactForm() {
  const [email, setEmail] = useState("");

  return (
    <form>
      <label htmlFor="contact-email">Email address</label>
      <input
        id="contact-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        aria-describedby="contact-email-help"
      />
      <p id="contact-email-help" className="help">
        We will never share your email.
      </p>
      <button type="submit">Send</button>
    </form>
  );
}
