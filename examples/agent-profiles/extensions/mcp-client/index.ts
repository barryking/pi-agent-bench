import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

type JsonObject = Record<string, unknown>;

interface ServerConfig {
	name: string;
	extension: string;
	transport: "stdio" | "http" | "sse";
	server: string;
	tools: string[];
}

class ExampleMcpClient {
	private process: ChildProcessWithoutNullStreams | undefined;
	private nextId = 1;
	private pending = new Map<
		number,
		{ resolve: (value: JsonObject) => void; reject: (error: Error) => void }
	>();
	private ready: Promise<void> | undefined;

	start(): Promise<void> {
		this.ready ??= this.initialize();
		return this.ready;
	}

	async callTool(name: string, arguments_: JsonObject): Promise<JsonObject> {
		await this.start();
		return this.request("tools/call", { name, arguments: arguments_ });
	}

	stop(): void {
		this.process?.kill();
		this.process = undefined;
	}

	private async initialize(): Promise<void> {
		const extensionDirectory = dirname(fileURLToPath(import.meta.url));
		this.process = spawn("python3", [join(extensionDirectory, "server.py")], {
			stdio: ["pipe", "pipe", "pipe"],
		});
		this.process.on("exit", (code) => {
			const error = new Error(`example MCP server stopped with code ${code}`);
			for (const waiter of this.pending.values()) waiter.reject(error);
			this.pending.clear();
		});
		const lines = createInterface({ input: this.process.stdout });
		lines.on("line", (line) => this.receive(line));
		const initialized = await this.request("initialize", {
			protocolVersion: "2025-06-18",
			capabilities: {},
			clientInfo: { name: "pi-agent-bench-example", version: "1.0.0" },
		});
		if (!initialized.serverInfo) {
			throw new Error("example MCP server returned no serverInfo");
		}
		this.notify("notifications/initialized", {});
		const listed = await this.request("tools/list", {});
		const tools = Array.isArray(listed.tools) ? listed.tools : [];
		if (!tools.some((tool) => (tool as JsonObject).name === "example_catalog_lookup")) {
			throw new Error("example MCP server did not advertise its catalog tool");
		}
	}

	private request(method: string, params: JsonObject): Promise<JsonObject> {
		const id = this.nextId++;
		return new Promise((resolve, reject) => {
			this.pending.set(id, { resolve, reject });
			this.write({ jsonrpc: "2.0", id, method, params });
		});
	}

	private notify(method: string, params: JsonObject): void {
		this.write({ jsonrpc: "2.0", method, params });
	}

	private write(message: JsonObject): void {
		if (!this.process) throw new Error("example MCP server is not running");
		this.process.stdin.write(`${JSON.stringify(message)}\n`);
	}

	private receive(line: string): void {
		let message: JsonObject;
		try {
			message = JSON.parse(line) as JsonObject;
		} catch {
			return;
		}
		const id = message.id;
		if (typeof id !== "number") return;
		const waiter = this.pending.get(id);
		if (!waiter) return;
		this.pending.delete(id);
		if (message.error) {
			waiter.reject(new Error(JSON.stringify(message.error)));
			return;
		}
		waiter.resolve((message.result as JsonObject) ?? {});
	}
}

function loadServerConfiguration(): ServerConfig {
	const configPath = process.env.PI_BENCH_MCP_CONFIG;
	if (!configPath) throw new Error("PI_BENCH_MCP_CONFIG is not set");
	const value = JSON.parse(readFileSync(configPath, "utf8")) as unknown;
	if (!Array.isArray(value)) throw new Error("MCP configuration must be a list");
	const server = value.find(
		(item) =>
			typeof item === "object" &&
			item !== null &&
			(item as ServerConfig).extension === "mcp-client" &&
			(item as ServerConfig).server === "example-catalog",
	) as ServerConfig | undefined;
	if (!server) throw new Error("example-catalog MCP server is not configured");
	if (server.transport !== "stdio") {
		throw new Error("the owned example supports only stdio MCP");
	}
	if (!Array.isArray(server.tools) || !server.tools.includes("example_catalog_lookup")) {
		throw new Error("example_catalog_lookup is missing from the MCP tool allowlist");
	}
	return server;
}

export default function exampleMcpExtension(pi: ExtensionAPI) {
	const server = loadServerConfiguration();
	const client = new ExampleMcpClient();

	pi.registerTool({
		name: "example_catalog_lookup",
		label: "Example catalog lookup",
		description: "Look up a widget or gadget through the owned example MCP server.",
		promptSnippet: "Look up a widget or gadget in the owned example MCP catalog",
		promptGuidelines: [
			"Use example_catalog_lookup only when the task asks about the example catalog.",
		],
		parameters: Type.Object({
			query: Type.String({ description: "Catalog item name, such as widget." }),
		}),
		async execute(_toolCallId, params) {
			const result = await client.callTool("example_catalog_lookup", {
				query: params.query,
			});
			const content = Array.isArray(result.content) ? result.content : [];
			return {
				content: content
					.filter((item) => (item as JsonObject).type === "text")
					.map((item) => ({
						type: "text" as const,
						text: String((item as JsonObject).text ?? ""),
					})),
				details: {
					server: server.server,
					transport: server.transport,
					isError: result.isError === true,
				},
			};
		},
	});

	pi.on("session_shutdown", async () => client.stop());
}
