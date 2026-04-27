/**
 * Generative-UI canvas (S3.8.3, F13).
 *
 * AUTO-REJECT guards encoded in the type:
 *   - sandbox is hard-coded to "allow-scripts" (FE-AP-4)
 *   - content arrives via `srcDoc`, NEVER `dangerouslySetInnerHTML`
 *     (FE-AP-12)
 *
 * `srcDoc` is a string the agent emits inside an `analysis_output`
 * `useComponent` slot; the iframe's `allow-scripts`-only sandbox prevents
 * the script from accessing the parent document, cookies, or storage.
 */

import * as React from "react";

export function SandboxedCanvas(props: {
  srcDoc: string;
  title: string;
  height?: number;
}): React.JSX.Element {
  return (
    <iframe
      title={props.title}
      sandbox="allow-scripts"
      srcDoc={props.srcDoc}
      className="w-full border border-border rounded-md bg-bg"
      style={{ height: `${props.height ?? 320}px` }}
    />
  );
}
