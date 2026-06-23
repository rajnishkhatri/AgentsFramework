/** Input + Textarea stories (PS1). */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Input } from "./input";
import { Textarea } from "./textarea";

const meta: Meta<typeof Input> = {
  title: "ui/Input",
  component: Input,
  args: { placeholder: "Search conversations…" },
};
export default meta;
type Story = StoryObj<typeof Input>;

export const Default: Story = {};
export const Disabled: Story = { args: { disabled: true, value: "disabled" } };

export const WithTextarea: Story = {
  render: () => (
    <div className="grid w-80 gap-3">
      <Input placeholder="Single line input" />
      <Textarea placeholder="Autosize textarea (field-sizing: content)" />
    </div>
  ),
};
