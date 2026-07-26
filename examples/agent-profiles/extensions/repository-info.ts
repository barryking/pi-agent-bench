import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { readdir } from "node:fs/promises";

export default function repositoryInfoExtension(pi: ExtensionAPI) {
	pi.registerTool({
		name: "repository_info",
		label: "Repository information",
		description: "List the top-level names in the current repository.",
		promptSnippet: "List top-level repository entries without running a shell command",
		promptGuidelines: [
			"Use repository_info when a quick top-level repository inventory is enough.",
		],
		parameters: Type.Object({}),
		async execute(_toolCallId, _params, _signal, _onUpdate, context) {
			const entries = (await readdir(context.cwd)).sort();
			return {
				content: [
					{
						type: "text",
						text: `BENCHMARK_EXTENSION_MARKER\nRepository: ${context.cwd}\nEntries:\n${entries.join("\n")}`,
					},
				],
				details: {
					cwd: context.cwd,
					entryCount: entries.length,
					marker: "BENCHMARK_EXTENSION_MARKER",
				},
			};
		},
	});
}
