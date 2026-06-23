/** Tooltip stories (PS1) — desktop hover affordance. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Tooltip, TooltipProvider, TooltipTrigger, TooltipContent } from "./tooltip";
import { Button } from "./button";

const meta: Meta<typeof Tooltip> = { title: "ui/Tooltip", component: Tooltip };
export default meta;
type Story = StoryObj<typeof Tooltip>;

export const OnButton: Story = {
  render: () => (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="sm">
            Hover me
          </Button>
        </TooltipTrigger>
        <TooltipContent>Copy answer</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ),
};
