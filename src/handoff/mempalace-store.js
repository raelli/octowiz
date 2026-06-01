class MemPalaceStore {
  async store(_type, _content, _metadata) {
    throw new Error("MemPalace not yet available — set HANDOFF_STORE=github or wait for aelli MemPalace API endpoint to be wired");
  }
  async fetch(_ref) {
    throw new Error("MemPalace not yet available — set HANDOFF_STORE=github or wait for aelli MemPalace API endpoint to be wired");
  }
}

module.exports = { MemPalaceStore };
