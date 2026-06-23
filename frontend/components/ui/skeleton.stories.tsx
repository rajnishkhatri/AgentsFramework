/** Skeleton stories (PS1) — streaming/loading placeholder. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Skeleton } from "./skeleton";

const meta: Meta<typeof Skeleton> = { title: "ui/Skeleton", component: Skeleton };
export default meta;
type Story = StoryObj<typeof Skeleton>;

export const MessagePlaceholder: Story = {
  render: () => (
    <div className="grid w-80 gap-2">
      <Skeleton className="h-3 w-40" />
      <Skeleton className="h-3 w-64" />
      <Skeleton className="h-3 w-52" />
    </div>
  ),
};
