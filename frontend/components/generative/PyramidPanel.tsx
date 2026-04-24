/**
 * Pyramid panel (S3.8.4, F14, feature-flagged).
 *
 * Renders `StructuredReasoning` analysis_output as an interactive issue
 * tree. Hidden by default behind the `pyramid_panel` feature flag (the
 * caller checks `featureFlagProvider.isEnabled('pyramid_panel')` before
 * mounting this component, P5 sync read).
 */

import * as React from "react";

export interface PyramidNode {
  readonly title: string;
  readonly summary?: string;
  readonly children?: ReadonlyArray<PyramidNode>;
}

export function PyramidPanel(props: { root: PyramidNode }): React.JSX.Element {
  return (
    <aside
      className="border border-border rounded-md px-4 py-3 bg-bg"
      aria-label="Reasoning pyramid"
    >
      <PyramidTree node={props.root} />
    </aside>
  );
}

function PyramidTree({ node }: { node: PyramidNode }): React.JSX.Element {
  return (
    <details open>
      <summary className="cursor-pointer font-semibold">{node.title}</summary>
      {node.summary ? (
        <p className="text-muted my-1">{node.summary}</p>
      ) : null}
      {node.children?.length ? (
        <ul className="pl-4 m-0">
          {node.children.map((c, i) => (
            <li key={i}>
              <PyramidTree node={c} />
            </li>
          ))}
        </ul>
      ) : null}
    </details>
  );
}
