/**
 * Storybook stories for SandboxedCanvas (FD6.STORY, S3.8.3).
 *
 * Validates that generative-UI renders in a sandboxed iframe with
 * `sandbox="allow-scripts"` only (FE-AP-4 AUTO-REJECT guard).
 * Content arrives via `srcDoc`, never `dangerouslySetInnerHTML` (FE-AP-12).
 */

import * as React from "react";
import { SandboxedCanvas } from "./SandboxedCanvas";

export default {
  title: "generative/SandboxedCanvas",
  component: SandboxedCanvas,
};

const SIMPLE_HTML = `
<!DOCTYPE html>
<html>
<body style="margin:0;padding:1rem;font-family:system-ui;background:#f9f7f5;color:#1f1e1d">
  <h2>Hello from the sandbox</h2>
  <p>This content renders inside <code>sandbox="allow-scripts"</code>.</p>
</body>
</html>
`;

const CHART_HTML = `
<!DOCTYPE html>
<html>
<body style="margin:0;padding:1rem;font-family:system-ui;background:#f9f7f5">
  <canvas id="c" width="300" height="200"></canvas>
  <script>
    const ctx = document.getElementById('c').getContext('2d');
    const data = [40, 80, 60, 100, 70];
    data.forEach((v, i) => {
      ctx.fillStyle = 'hsl(' + (i * 60) + ' 70% 50%)';
      ctx.fillRect(i * 60 + 5, 200 - v, 50, v);
    });
  </script>
</body>
</html>
`;

const EMPTY_HTML = `
<!DOCTYPE html>
<html>
<body style="margin:0;padding:1rem;font-family:system-ui;color:#888">
  <em>No output generated.</em>
</body>
</html>
`;

export function SimpleContent(): React.JSX.Element {
  return <SandboxedCanvas srcDoc={SIMPLE_HTML} title="Simple generative output" />;
}

export function ChartVisualization(): React.JSX.Element {
  return (
    <SandboxedCanvas
      srcDoc={CHART_HTML}
      title="Bar chart visualization"
      height={240}
    />
  );
}

export function EmptyOutput(): React.JSX.Element {
  return <SandboxedCanvas srcDoc={EMPTY_HTML} title="Empty canvas" height={100} />;
}

export function TallCanvas(): React.JSX.Element {
  return (
    <SandboxedCanvas
      srcDoc={SIMPLE_HTML}
      title="Tall canvas"
      height={600}
    />
  );
}
