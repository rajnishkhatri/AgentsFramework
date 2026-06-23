/** DropdownMenu stories (PS1) — per-message actions (copy/regenerate/edit). */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Copy, RotateCw, Pencil } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "./dropdown-menu";
import { Button } from "./button";

const meta: Meta<typeof DropdownMenu> = {
  title: "ui/DropdownMenu",
  component: DropdownMenu,
};
export default meta;
type Story = StoryObj<typeof DropdownMenu>;

export const MessageActions: Story = {
  render: () => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm">
          ⋯
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuItem>
          <Copy className="size-4" /> Copy
        </DropdownMenuItem>
        <DropdownMenuItem>
          <RotateCw className="size-4" /> Regenerate
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem>
          <Pencil className="size-4" /> Edit
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  ),
};
