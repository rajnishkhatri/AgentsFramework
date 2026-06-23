/**
 * Storybook stories for Composer (FD6.STORY, S3.8.5) — P3 §5 responsive.
 *
 * The composer adapts to its own SLOT width via a container query
 * (`@container/composer`), not the viewport: in a wide slot the model-picker
 * shows its full label; in a narrow slot (phone column / drawer) the label
 * collapses to just the chevron. These stories render it at fixed slot widths
 * so the container-query behaviour is visible in Storybook (the §5 gate).
 */

import * as React from "react";
import { Composer } from "./Composer";

export default {
  title: "chat/Composer",
  component: Composer,
};

const noop = (): void => {};

/** Default: a comfortable desktop slot — full model label shown. */
export function Default(): React.JSX.Element {
  return (
    <div style={{ width: "48rem", maxWidth: "100%" }}>
      <Composer onSend={noop} />
    </div>
  );
}

/** Wide slot (Mac window) — model label visible, roomy toolbar. */
export function WideSlot(): React.JSX.Element {
  return (
    <div style={{ width: "40rem" }}>
      <Composer onSend={noop} />
    </div>
  );
}

/**
 * Narrow slot (phone column / drawer, < 20rem) — the model label collapses to
 * the chevron via the container query; send + add affordances stay.
 */
export function NarrowSlot(): React.JSX.Element {
  return (
    <div style={{ width: "18rem" }}>
      <Composer onSend={noop} />
    </div>
  );
}

/** Busy (a run in flight) — send puck disabled. */
export function Busy(): React.JSX.Element {
  return (
    <div style={{ width: "40rem" }}>
      <Composer onSend={noop} busy />
    </div>
  );
}
