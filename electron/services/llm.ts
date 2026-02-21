import { AppConfig } from "./types";

interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface ChatCompletionResponse {
  choices: Array<{ message: { content: string } }>;
}

export async function callLlm(config: AppConfig, messages: ChatMessage[]): Promise<string> {
  if (config.mockMode) {
    return [
      "【Mock输出】",
      messages.map((m) => `${m.role.toUpperCase()}: ${m.content.slice(0, 140)}`).join("\n")
    ].join("\n\n");
  }

  const endpoint = config.endpoint.replace(/\/$/, "");
  const response = await fetch(`${endpoint}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${config.apiKey}`
    },
    body: JSON.stringify({
      model: config.model,
      temperature: config.temperature,
      messages
    })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`LLM调用失败(${response.status}): ${text}`);
  }

  const data = (await response.json()) as ChatCompletionResponse;
  return data.choices?.[0]?.message?.content ?? "";
}
