/** Toast stories (PS1) — errors / cancel notifications (sonner). */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Toaster, toast } from "./toast";
import { Button } from "./button";

const meta: Meta<typeof Toaster> = { title: "ui/Toast", component: Toaster };
export default meta;
type Story = StoryObj<typeof Toaster>;

export const CancelAndError: Story = {
  render: () => (
    <div className="flex gap-3">
      <Toaster />
      <Button variant="outline" onClick={() => toast("Run cancelled")}>
        Cancel toast
      </Button>
      <Button variant="outline" onClick={() => toast.error("Stream failed")}>
        Error toast
      </Button>
    </div>
  ),
};
