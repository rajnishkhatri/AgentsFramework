/** ScrollArea stories (PS1) — message/thread scroll container. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { ScrollArea } from "./scroll-area";

const meta: Meta<typeof ScrollArea> = {
  title: "ui/ScrollArea",
  component: ScrollArea,
};
export default meta;
type Story = StoryObj<typeof ScrollArea>;

export const ThreadList: Story = {
  render: () => (
    <ScrollArea className="h-48 w-64 rounded-md border border-border">
      <div className="grid gap-1 p-2 text-sm text-fg">
        {Array.from({ length: 20 }, (_, i) => (
          <div key={i} className="rounded-sm px-2 py-1 hover:bg-selected">
            Conversation {i + 1}
          </div>
        ))}
      </div>
    </ScrollArea>
  ),
};
