"use strict";
const { subscribe, updateTask } = require("./a2a-client");

async function onTask(task) {
  const { id, messages } = task;
  await updateTask(id, "working");
  try {
    const text = messages?.[0]?.parts?.[0]?.text;
    const parsed = text ? JSON.parse(text) : {};
    await updateTask(id, "completed", {
      name: "aelli-response",
      parts: [{ kind: "text", text: parsed.response || "received" }],
    });
  } catch {
    await updateTask(id, "completed", {
      name: "aelli-response",
      parts: [{ kind: "text", text: "received" }],
    });
  }
}

subscribe(onTask);
