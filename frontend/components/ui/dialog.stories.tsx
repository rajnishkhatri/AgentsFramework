/** Dialog stories (PS1). */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "./dialog";
import { Button } from "./button";

const meta: Meta<typeof Dialog> = { title: "ui/Dialog", component: Dialog };
export default meta;
type Story = StoryObj<typeof Dialog>;

export const Confirm: Story = {
  render: () => (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="outline">Delete chat…</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Delete this conversation?</DialogTitle>
        <DialogDescription>
          This removes the thread. Recalled memories are kept.
        </DialogDescription>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm">
            Cancel
          </Button>
          <Button size="sm">Delete</Button>
        </div>
      </DialogContent>
    </Dialog>
  ),
};
