/**
 * Pure learn-identity resolver (eng-coach-workos-learner-identity).
 *
 * Maps WorkOS session (or E2E bypass) → learnerId / displayName / seedMode.
 * No React; called from the (coach) RSC layout before LearnIdentityProvider.
 */

/**
 * Demo learner id for E2E bypass. Kept as a local constant (not imported from
 * `_dev_seed`) so this pure learn/ helper stays adapter-free (C1/F1).
 * Must stay byte-identical to `_dev_seed.DEV_LEARNER_ID` ("Garvit").
 */
const DEMO_LEARNER_ID = "Garvit";

export type SeedMode = "demo" | "fresh";

export type LearnIdentity = {
  readonly learnerId: string;
  readonly displayName: string;
  readonly seedMode: SeedMode;
};

/** Minimal WorkOS AuthKit user shape used for learn identity (Q-C2-A). */
export type WorkOsLearnUser = {
  readonly id: string;
  readonly firstName?: string | null;
  readonly email?: string | null;
};

function displayNameFromUser(user: WorkOsLearnUser): string {
  const first = user.firstName?.trim();
  if (first) return first;
  const email = user.email?.trim();
  if (email) {
    const local = email.split("@")[0]?.trim();
    if (local) return local;
  }
  return "Learner";
}

/**
 * Resolve the learner identity for `/learn/*`.
 *
 * - bypass → demo Garvit + full corpus seed
 * - authenticated user → WorkOS id + fresh slate
 * - no bypass and no user → throw (FR-1: never invent Garvit)
 */
export function resolveLearnIdentity(args: {
  bypass: boolean;
  user: WorkOsLearnUser | null;
}): LearnIdentity {
  if (args.bypass) {
    return {
      learnerId: DEMO_LEARNER_ID,
      displayName: "Garvit",
      seedMode: "demo",
    };
  }
  if (args.user == null) {
    throw new Error(
      "resolveLearnIdentity: signed-in WorkOS user required when E2E bypass is off",
    );
  }
  return {
    learnerId: args.user.id,
    displayName: displayNameFromUser(args.user),
    seedMode: "fresh",
  };
}
