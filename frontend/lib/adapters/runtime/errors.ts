/**
 * Typed error hierarchy for AgentRuntimeClient adapters (P4 / FD2.A5).
 *
 * Each subclass corresponds to one HTTP-level failure mode. The translation
 * table is documented per-adapter in JSDoc; callers (UI components, BFF
 * routes) may switch on the concrete class to tailor the error UI.
 */

export class AgentRuntimeError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = new.target.name;
  }
}

export class AgentAuthError extends AgentRuntimeError {}
export class AgentAuthorizationError extends AgentRuntimeError {}
export class AgentRateLimitError extends AgentRuntimeError {}
export class AgentServerError extends AgentRuntimeError {}
export class AgentNetworkError extends AgentRuntimeError {}
