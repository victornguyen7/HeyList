import type { AgAiConversationItem, AgAiEvent, AgAiOutputItem, AgLlmAdapter, AgLlmRequest, AgLlmResponse } from "ag-studio";

// AG Studio's agents reach a model only through an adapter (decision 62). This one sends each turn to HeyList's
// backend (POST /api/studio/chat), which calls Ollama with the key on the server; Studio runs the tool calls.
// Ollama doesn't stream through the proxy here, so a turn's events are sent in one go once the reply arrives.

type OllamaMessage = { role: string; content: string; tool_name?: string; tool_calls?: { function: { name: string; arguments: object } }[] };
type Turn = { content: string; toolCalls: { name: string; arguments: object }[]; usage: { inputTokens: number; outputTokens: number } };

const text = (parts: { type: string; text?: string; refusal?: string }[]) => parts.map((p) => p.text ?? p.refusal ?? "").join("");

function parseArgs(json: string): object {
  try {
    return JSON.parse(json || "{}");
  } catch {
    return {};
  }
}

/** Studio's conversation as Ollama chat messages. Tool calls in a row become one assistant message. */
export function toOllama(request: AgLlmRequest): OllamaMessage[] {
  const messages: OllamaMessage[] = [];
  let system = request.instructions ?? "";
  if (request.toolChoice === "required") system += "\nCall at least one tool in this reply.";
  else if (typeof request.toolChoice === "object") system += `\nCall the ${request.toolChoice.name} tool in this reply.`;
  if (system) messages.push({ role: "system", content: system });

  const toolNames = new Map<string, string>();
  for (const item of request.input as AgAiConversationItem[]) {
    if (item.type === "message") {
      messages.push({ role: item.role, content: text(item.content) });
    } else if (item.type === "function_call") {
      toolNames.set(item.callId, item.name);
      const call = { function: { name: item.name, arguments: parseArgs(item.arguments) } };
      const last = messages.at(-1);
      if (last?.role === "assistant" && last.tool_calls && !last.content) last.tool_calls.push(call);
      else messages.push({ role: "assistant", content: "", tool_calls: [call] });
    } else if (item.type === "function_call_output") {
      messages.push({ role: "tool", content: item.output, tool_name: toolNames.get(item.callId) });
    }
    // Reasoning items are the model's own notes; they aren't sent back.
  }
  return messages;
}

export function ollamaAdapter(endpoint = "/api/studio/chat"): AgLlmAdapter {
  return {
    executeTurn(request, options) {
      const id = crypto.randomUUID();
      const tools =
        request.toolChoice === "none"
          ? []
          : (request.tools ?? []).filter((tool) => tool.kind !== "provided").map((tool) => ({ type: "function", function: { name: tool.name, description: tool.description, parameters: tool.parameters } }));

      const turn: Promise<Turn> = fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: toOllama(request), tools, format: request.responseFormat?.type === "json" ? request.responseFormat.schema : undefined }),
        signal: options?.signal,
      }).then(async (res) => {
        if (!res.ok) throw new Error(res.status === 429 ? "The dashboard assistant has been used a lot this hour. Try again later." : "The dashboard assistant isn't available right now.");
        return res.json();
      });

      const complete: Promise<AgLlmResponse> = turn.then(
        ({ content, toolCalls, usage }) => {
          const output: AgAiOutputItem[] = [];
          if (content) output.push({ id: `${id}-m`, kind: "output", type: "message", role: "assistant", status: "completed", content: [{ type: "text", text: content, annotations: [] }] });
          toolCalls.forEach((call, index) =>
            output.push({ id: `${id}-t${index}`, kind: "output", type: "function_call", callId: `${id}-c${index}`, name: call.name, arguments: JSON.stringify(call.arguments), status: "completed" }),
          );
          return { id, createdAt: Date.now(), status: "completed", output, usage: { inputTokens: usage.inputTokens, outputTokens: usage.outputTokens } } as AgLlmResponse;
        },
        (err: Error) => ({ id, createdAt: Date.now(), status: options?.signal?.aborted ? "cancelled" : "failed", output: [], error: { code: "turn_failed", message: err.message } }),
      );

      return {
        complete,
        stream: {
          async *[Symbol.asyncIterator]() {
            const response = await complete;
            for (const item of response.output) {
              if (item.type === "message") yield { type: "TEXT_MESSAGE_CHUNK", messageId: item.id, role: "assistant", delta: text(item.content) } as AgAiEvent;
              else if (item.type === "function_call") yield { type: "TOOL_CALL_CHUNK", toolCallId: item.callId, toolCallName: item.name, delta: item.arguments } as AgAiEvent;
            }
          },
        },
      };
    },
  };
}
