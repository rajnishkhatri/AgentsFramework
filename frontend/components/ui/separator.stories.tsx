/** Separator stories (PS1) — hairline divider. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Separator } from "./separator";

const meta: Meta<typeof Separator> = { title: "ui/Separator", component: Separator };
export default meta;
type Story = StoryObj<typeof Separator>;

export const Horizontal: Story = {
  render: () => (
    <div className="w-64 text-sm text-fg">
      <p>Above</p>
      <Separator className="my-3" />
      <p>Below</p>
    </div>
  ),
};

export const Vertical: Story = {
  render: () => (
    <div className="flex h-8 items-center gap-3 text-sm text-fg">
      <span>Chats</span>
      <Separator orientation="vertical" />
      <span>Memory</span>
    </div>
  ),
};
