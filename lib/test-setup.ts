class MockBroadcastChannel {
  static channels: Map<string, Set<MockBroadcastChannel>> = new Map();
  
  name: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onmessageerror: ((event: MessageEvent) => void) | null = null;
  
  constructor(name: string) {
    this.name = name;
    if (!MockBroadcastChannel.channels.has(name)) {
      MockBroadcastChannel.channels.set(name, new Set());
    }
    MockBroadcastChannel.channels.get(name)!.add(this);
  }
  
  postMessage(message: any): void {
    const channels = MockBroadcastChannel.channels.get(this.name);
    if (channels) {
      for (const channel of channels) {
        if (channel !== this && channel.onmessage) {
          channel.onmessage(new MessageEvent("message", { data: message }));
        }
      }
    }
  }
  
  close(): void {
    const channels = MockBroadcastChannel.channels.get(this.name);
    if (channels) {
      channels.delete(this);
    }
  }
  
  static clearAll(): void {
    MockBroadcastChannel.channels.clear();
  }
}

global.BroadcastChannel = MockBroadcastChannel as any;
global.window.BroadcastChannel = MockBroadcastChannel as any;