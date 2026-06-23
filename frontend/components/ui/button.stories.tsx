/** Button stories (PS1) — §2.6 accent rationing across variants/sizes. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { ArrowUp } from "lucide-react";
import { Button } from "./button";

const meta: Meta<typeof Button> = {
  title: "ui/Button",
  component: Button,
  args: { children: "Button" },
  argTypes: {
    variant: { control: "select", options: ["default", "outline", "ghost"] },
    size: { control: "select", options: ["sm", "md"] },
  },
};
export default meta;
type Story = StoryObj<typeof Button>;

export const Default: Story = {};
export const Outline: Story = { args: { variant: "outline" } };
export const Ghost: Story = { args: { variant: "ghost" } };
export const Disabled: Story = { args: { disabled: true } };

export const Sizes: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button size="sm">sm</Button>
      <Button size="md">md</Button>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button>default</Button>
      <Button variant="outline">outline</Button>
      <Button variant="ghost">ghost</Button>
    </div>
  ),
};
