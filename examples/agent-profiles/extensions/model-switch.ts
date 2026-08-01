import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function modelSwitchExtension(pi: ExtensionAPI) {
	let switched = false;
	pi.on("message_end", async (event, ctx) => {
		if (switched) return;
		if (event.message.role !== "assistant") return;
		const reviewer = ctx.modelRegistry.find("inspect-bridge", "review-model");
		if (!reviewer) throw new Error("review-model is not available to this agent profile");
		if (!(await pi.setModel(reviewer))) {
			throw new Error("review-model could not be selected");
		}
		switched = true;
	});
}
