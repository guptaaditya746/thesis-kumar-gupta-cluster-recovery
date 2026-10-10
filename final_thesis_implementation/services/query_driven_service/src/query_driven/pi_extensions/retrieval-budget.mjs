import { execFile } from "node:child_process";
import { open } from "node:fs/promises";
import { promisify } from "node:util";
import { Type } from "@mariozechner/pi-ai";

const execFileAsync = promisify(execFile);

function positiveNumber(name, fallback) {
  const value = Number(process.env[name]);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}


export default function retrievalBudget(pi) {
  const maxTools = Math.floor(positiveNumber("QD_SEARCH_MAX_TOOLS", 50));
  const maxSeconds = positiveNumber("QD_SEARCH_MAX_SECONDS", 300);
  const maxOutputTokens = Math.floor(positiveNumber("QD_MAX_OUTPUT_TOKENS", 2048));
  const deadline = Date.now() + maxSeconds * 1000;
  let admittedTools = 0;
  const seenToolCalls = new Set();

  pi.registerTool({
    name: "search_jsonl",
    label: "Search JSONL corpus",
    description:
      "Search the configured JSONL corpus and return compact candidates with exact document_id and byte_offset values. Use exact_title=true for named works and people.",
    promptSnippet: "Search the JSONL corpus with exact record references",
    parameters: Type.Object({
      query: Type.String({ description: "Distinctive title, entity, or phrase" }),
      exact_title: Type.Optional(
        Type.Boolean({ description: "Match the JSON-encoded record title exactly" }),
      ),
      max_results: Type.Optional(
        Type.Integer({ minimum: 1, maximum: 12, description: "Maximum candidates" }),
      ),
    }),
    execute: async (_toolCallId, params) => {
      const corpusFile = process.env.QD_CORPUS_FILE || "wiki_dump.jsonl";
      const documentIdField = process.env.QD_DOCUMENT_ID_FIELD || "id";
      const documentContentField = process.env.QD_DOCUMENT_CONTENT_FIELD || "text";
      const maxRecordBytes = Math.floor(
        positiveNumber("QD_MAX_DOCUMENT_BYTES", 4 * 1024 * 1024),
      );
      const maxResults = Math.min(Math.max(params.max_results || 12, 1), 12);
      const pattern =
        params.exact_title === false
          ? params.query
          : `\\\"${params.query}\\\"\\n`;
      const args = [
        "-b",
        "-i",
        "-F",
        "-m",
        String(maxResults),
        "--max-columns",
        "1200",
        "--max-columns-preview",
        "--",
        pattern,
        corpusFile,
      ];
      let stdout = "";
      try {
        ({ stdout } = await execFileAsync("rg", args, {
          cwd: process.cwd(),
          timeout: 30000,
          maxBuffer: 64 * 1024,
          encoding: "utf8",
        }));
      } catch (error) {
        stdout = typeof error?.stdout === "string" ? error.stdout : "";
        if (!stdout && error?.code !== 1) {
          throw error;
        }
      }
      const offsets = stdout
        .split("\n")
        .map((line) => Number(line.slice(0, line.indexOf(":"))))
        .filter((offset) => Number.isSafeInteger(offset) && offset >= 0);
      const results = [];
      const corpusHandle = await open(corpusFile, "r");
      try {
        const buffer = Buffer.alloc(maxRecordBytes + 1);
        for (const byteOffset of offsets) {
          const { bytesRead } = await corpusHandle.read(
            buffer, 0, buffer.length, byteOffset,
          );
          if (bytesRead === 0) continue;
          const newline = buffer.indexOf(0x0a, 0);
          if (newline < 0 && bytesRead > maxRecordBytes) continue;
          const recordEnd = newline >= 0 && newline < bytesRead ? newline : bytesRead;
          let record;
          try {
            record = JSON.parse(buffer.toString("utf8", 0, recordEnd));
          } catch {
            continue;
          }
          const documentId = record?.[documentIdField];
          const content = record?.[documentContentField];
          if (
            !["string", "number"].includes(typeof documentId) ||
            typeof content !== "string"
          ) continue;
          results.push({
            document_id: String(documentId),
            byte_offset: byteOffset,
            preview: content.slice(0, 1000),
          });
        }
      } finally {
        await corpusHandle.close();
      }
      const text = JSON.stringify({ corpus_file: corpusFile, results }, null, 2);
      return {
        content: [{ type: "text", text }],
        details: { count: results.length },
      };
    },
  });

  pi.on("before_provider_request", async (event) => {
    if (!event.payload || typeof event.payload !== "object") {
      return undefined;
    }

    const payload = { ...event.payload };
    if (Object.hasOwn(payload, "max_completion_tokens")) {
      payload.max_completion_tokens = Math.min(
        Number(payload.max_completion_tokens) || maxOutputTokens,
        maxOutputTokens,
      );
    } else {
      payload.max_tokens = Math.min(
        Number(payload.max_tokens) || maxOutputTokens,
        maxOutputTokens,
      );
    }
    return payload;
  });

  pi.on("tool_call", async (event) => {
    if (event.toolName === "write" || event.toolName === "edit") {
      return { block: true, reason: "Retrieval is read-only." };
    }

    if (admittedTools >= maxTools || Date.now() >= deadline) {
      return {
        block: true,
        reason:
          "Search budget exhausted. Do not call another tool. " +
          "Use only verified evidence already inspected and emit the final " +
          "<retrieval_result> block now; return an empty documents list if necessary.",
      };
    }

    admittedTools += 1;
    const signature = `${event.toolName}:${JSON.stringify(event.input)}`;
    if (seenToolCalls.has(signature)) {
      return {
        block: true,
        reason:
          "This exact tool call already ran. Use its existing evidence, refine " +
          "the query with a distinctive entity, or emit the final <retrieval_result> block.",
      };
    }
    seenToolCalls.add(signature);
    return undefined;
  });
}
