/** Tabs stories (PS1) — SidebarTabBar (Chats | Memory), selected fill. */
import type { Meta, StoryObj } from "@storybook/nextjs-vite";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./tabs";

const meta: Meta<typeof Tabs> = { title: "ui/Tabs", component: Tabs };
export default meta;
type Story = StoryObj<typeof Tabs>;

export const ChatsMemory: Story = {
  render: () => (
    <Tabs defaultValue="chats" className="w-72">
      <TabsList>
        <TabsTrigger value="chats">Chats</TabsTrigger>
        <TabsTrigger value="memory">Memory</TabsTrigger>
      </TabsList>
      <TabsContent value="chats" className="pt-3 text-sm text-muted">
        Thread list…
      </TabsContent>
      <TabsContent value="memory" className="pt-3 text-sm text-muted">
        Recalled memories…
      </TabsContent>
    </Tabs>
  ),
};
