/** Card stories (PS1) — radius-lg surface chrome. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Card, CardHeader, CardTitle, CardContent } from "./card";

const meta: Meta<typeof Card> = { title: "ui/Card", component: Card };
export default meta;
type Story = StoryObj<typeof Card>;

export const Default: Story = {
  render: () => (
    <Card className="w-80">
      <CardHeader>
        <CardTitle>Exit gate and what's next</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted">
        Phase 6's done-when checklist is complete in code.
      </CardContent>
    </Card>
  ),
};
