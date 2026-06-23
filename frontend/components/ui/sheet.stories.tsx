/** Sheet stories (PS1) — mobile thread drawer (left) + reasoning sheet (bottom). */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Sheet, SheetTrigger, SheetContent, SheetTitle } from "./sheet";
import { Button } from "./button";

const meta: Meta<typeof Sheet> = { title: "ui/Sheet", component: Sheet };
export default meta;
type Story = StoryObj<typeof Sheet>;

export const LeftDrawer: Story = {
  render: () => (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline">Open thread drawer</Button>
      </SheetTrigger>
      <SheetContent side="left" className="p-4">
        <SheetTitle>Conversations</SheetTitle>
        <div className="mt-3 grid gap-1 text-sm text-muted">
          <span>Today</span>
          <span>· thread one</span>
          <span>· thread two</span>
        </div>
      </SheetContent>
    </Sheet>
  ),
};

export const BottomSheet: Story = {
  render: () => (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="outline">Open reasoning sheet</Button>
      </SheetTrigger>
      <SheetContent side="bottom" className="p-4">
        <SheetTitle>Reasoning / tools</SheetTitle>
        <div className="mt-3 text-sm text-muted">▸ step 1 · plan</div>
      </SheetContent>
    </Sheet>
  ),
};
