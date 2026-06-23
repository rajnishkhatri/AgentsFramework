/** Badge stories (PS1). */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Badge } from "./badge";

const meta: Meta<typeof Badge> = {
  title: "ui/Badge",
  component: Badge,
  args: { children: "badge" },
  argTypes: {
    variant: { control: "select", options: ["default", "accent", "outline"] },
  },
};
export default meta;
type Story = StoryObj<typeof Badge>;

export const Default: Story = {};
export const Accent: Story = { args: { variant: "accent", children: "eval" } };
export const Outline: Story = { args: { variant: "outline" } };
export const All: Story = {
  render: () => (
    <div className="flex items-center gap-2">
      <Badge>default</Badge>
      <Badge variant="accent">accent</Badge>
      <Badge variant="outline">outline</Badge>
    </div>
  ),
};
