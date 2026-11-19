"use strict";

const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const sendButton = document.querySelector("#send-button");
const chatLog = document.querySelector("#chat-log");
const suggestions = document.querySelector(".suggestions");
let isResponding = false;
const conversation = [];
const MAX_HISTORY_MESSAGES = 16;

function appendMessage(role, text) {
  const article = document.createElement("article");
  article.className = `message ${role}-message`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "assistant" ? "C" : "Y";

  const content = document.createElement("div");
  content.className = "message-content";

  const speaker = document.createElement("span");
  speaker.className = "speaker";
  speaker.textContent = role === "assistant" ? "COACH COURTSIDE" : "YOU";

  const paragraph = document.createElement("p");
  paragraph.textContent = text;

  content.append(speaker, paragraph);
  article.append(avatar, content);
  chatLog.append(article);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showTypingIndicator() {
  const indicator = document.createElement("article");
  indicator.className = "message assistant-message typing-indicator";
  indicator.setAttribute("aria-label", "Coach is thinking");

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = "C";

  const content = document.createElement("div");
  content.className = "message-content";
  const speaker = document.createElement("span");
  speaker.className = "speaker";
  speaker.textContent = "COACH COURTSIDE";
  const dots = document.createElement("p");
  dots.setAttribute("aria-hidden", "true");
  for (let index = 0; index < 3; index += 1) {
    const dot = document.createElement("i");
    dots.append(dot);
  }
  content.append(speaker, dots);
  indicator.append(avatar, content);
  chatLog.append(indicator);
  chatLog.scrollTop = chatLog.scrollHeight;
  return indicator;
}

async function sendMessage(text) {
  const question = text.trim();
  if (!question || isResponding) {
    return;
  }

  appendMessage("user", question);
  conversation.push({ role: "user", content: question });
  input.value = "";
  isResponding = true;
  sendButton.disabled = true;
  suggestions.hidden = true;
  const indicator = showTypingIndicator();

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: conversation.slice(-MAX_HISTORY_MESSAGES) }),
    });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || `The AI request failed (${response.status}).`);
    }
    if (typeof result.reply !== "string" || !result.reply.trim()) {
      throw new Error("The AI returned an empty response. Please try again.");
    }
    conversation.push({ role: "assistant", content: result.reply });
    if (conversation.length > MAX_HISTORY_MESSAGES) {
      conversation.splice(0, conversation.length - MAX_HISTORY_MESSAGES);
    }
    indicator.remove();
    appendMessage("assistant", result.reply);
  } catch (error) {
    indicator.remove();
    const detail = error instanceof Error ? error.message : "Unknown connection error.";
    appendMessage("assistant", `I couldn't get a reply: ${detail}`);
  } finally {
    isResponding = false;
    sendButton.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(input.value);
});

suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-prompt]");
  if (button) {
    sendMessage(button.dataset.prompt);
  }
});
