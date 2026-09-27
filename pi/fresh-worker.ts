import {
    createAgentSession,
    SessionManager,
    type ExtensionAPI,
} from "@earendil-works/pi-coding-agent";

import { Type } from "typebox";

interface FreshWorkerDetails {
    sessionId: string;
    sessionFile?: string;
    model: string;
    thinkingLevel?: string;
    done: boolean;
}

interface FreshWorkerContext {
    model?: { provider: string; id: string };
    thinkingLevel?: string;
    cwd?: string;
    signal?: AbortSignal;
}

function getFinalAssistantText(messages: readonly any[]): string {
    for (let i = messages.length - 1; i >= 0; i--) {
        const message = messages[i];

        if (!message || message.role !== "assistant") {
            continue;
        }

        if (typeof message.content === "string") {
            return message.content;
        }

        if (Array.isArray(message.content)) {
            const parts: string[] = [];

            for (const part of message.content) {
                if (
                    part &&
                    part.type === "text" &&
                    typeof part.text === "string"
                ) {
                    parts.push(part.text);
                }
            }

            if (parts.length > 0) {
                return parts.join("");
            }
        }
    }

    return "";
}

/**
 * Run one Fresh Worker.
 *
 * Creates a completely new Pi session using the caller's current model and
 * thinking level. No parent conversation messages are copied and all tools are
 * disabled in the worker session.
 */
export async function runFreshWorker(
    ctx: FreshWorkerContext,
    prompt: string,
    onUpdate?: (details: any) => void
): Promise<{ content: any[]; details: FreshWorkerDetails }> {
    const trimmed = (prompt || "").trim();

    if (!trimmed) {
        throw new Error("Fresh Worker prompt must not be empty.");
    }

    if (!ctx.model) {
        throw new Error(
            "Fresh Worker cannot start because the parent Pi session has no active model."
        );
    }

    const modelName = `${ctx.model.provider}/${ctx.model.id}`;
    const thinkingLevel = ctx.thinkingLevel ?? "off";
    const cwd = ctx.cwd ?? process.cwd();

    onUpdate?.({
        content: [
            {
                type: "text",
                text: `Starting fresh worker with ${modelName}...`,
            },
        ],
        details: {
            model: modelName,
            done: false,
        },
    });

    /*
     * Create a completely new saved Pi session.
     *
     * Isolation contract:
     * - no parent messages are copied
     * - no tools are available
     * - Fresh Worker itself is therefore unavailable to the child
     * - the active parent model is reused
     * - the active parent thinking level is reused
     */
    const sessionManager = SessionManager.create(cwd);

    const { session } = await createAgentSession({
        cwd,
        model: ctx.model,
        thinkingLevel,
        noTools: "all",
        sessionManager,
    });

    let streamedText = "";

    const unsubscribe = session.subscribe((event: any) => {
        if (
            event?.type === "message_update" &&
            event.assistantMessageEvent?.type === "text_delta" &&
            typeof event.assistantMessageEvent.delta === "string"
        ) {
            streamedText += event.assistantMessageEvent.delta;
        }
    });

    const abortHandler = () => {
        void session.abort();
    };

    const signal = ctx.signal;

    if (signal) {
        if (signal.aborted) {
            abortHandler();
        } else {
            signal.addEventListener("abort", abortHandler, { once: true });
        }
    }

    try {
        await session.prompt(trimmed);

        const finalText =
            getFinalAssistantText(session.messages).trim() ||
            streamedText.trim();

        if (!finalText) {
            throw new Error(
                "Fresh Worker completed without an assistant response."
            );
        }

        const details: FreshWorkerDetails = {
            sessionId: session.sessionId,
            sessionFile: session.sessionFile,
            model: modelName,
            thinkingLevel,
            done: true,
        };

        return {
            content: [
                {
                    type: "text",
                    text: finalText,
                },
            ],
            details,
        };
    } catch (error) {
        if (ctx.signal?.aborted) {
            throw new Error("Fresh Worker was cancelled.");
        }

        if (error instanceof Error) {
            throw error;
        }

        throw new Error(`Fresh Worker failed: ${String(error)}`);
    } finally {
        unsubscribe();

        if (ctx.signal) {
            ctx.signal.removeEventListener("abort", abortHandler);
        }

        session.dispose();
    }
}

export default function freshWorkerExtension(pi: ExtensionAPI) {
    pi.registerTool({
        name: "fresh_worker",
        label: "Fresh Worker",
        description:
            "Run one bounded task in a completely fresh Pi session using the current model and thinking level. " +
            "The worker receives no parent conversation history and has no tools. " +
            "Use it when a task benefits from a clean independent context.",
        parameters: Type.Object({
            prompt: Type.String({
                minLength: 1,
                description:
                    "The complete self-contained instruction for the fresh worker.",
            }),
        }),
        async execute(
            _toolCallId,
            params,
            signal,
            onUpdate,
            ctx
        ) {
            return runFreshWorker(
                { ...ctx, signal: signal ?? ctx.signal },
                String(params.prompt ?? ""),
                (info) => onUpdate?.(info)
            );
        },
    });
}
