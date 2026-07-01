import AppIntents

/// Exposes "Ask Conductor" to Siri and Shortcuts. Not verified against a
/// real build (see README) — App Intents' macro-generated conformances are
/// sensitive to exact Xcode/SDK versions, so double-check this compiles
/// as-is before relying on it.
public struct AskConductorIntent: AppIntent {
    public static var title: LocalizedStringResource = "Ask Conductor"
    public static var description = IntentDescription(
        "Ask your Conductor voice assistant a question and hear the answer."
    )

    @Parameter(title: "Question")
    public var question: String

    public init() {}

    public init(question: String) {
        self.question = question
    }

    public func perform() async throws -> some IntentResult & ProvidesDialog {
        let client = ConductorClient()
        let response = try await client.chat(query: question)
        return .result(dialog: IntentDialog(stringLiteral: response.response))
    }
}

/// Groups the intent under Siri's "Conductor" app shortcuts so it's
/// discoverable without the user having to record a custom phrase first.
public struct ConductorShortcuts: AppShortcutsProvider {
    public static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: AskConductorIntent(),
            phrases: [
                "Ask \(.applicationName) \(\.$question)",
                "Ask \(.applicationName)"
            ],
            shortTitle: "Ask Conductor",
            systemImageName: "mic.fill"
        )
    }
}
