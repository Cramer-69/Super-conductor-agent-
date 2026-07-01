import Foundation
import Observation

@MainActor
@Observable
final class AppModel {
    private(set) var messages: [ChatMessage] = [
        ChatMessage(
            role: .assistant,
            text: "I’m ARA. The OpenAI-led Council is connected. What outcome are we moving forward?"
        )
    ]
    private(set) var health: HealthResponse?
    private(set) var isSending = false
    private(set) var isCheckingHealth = false
    private(set) var errorMessage: String?

    private let api: ConductorAPI
    private var conversationID: String?

    init(api: ConductorAPI = ConductorAPI()) {
        self.api = api
    }

    func send(_ text: String) async {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isSending else { return }

        messages.append(ChatMessage(role: .user, text: trimmed))
        isSending = true
        errorMessage = nil

        do {
            let result = try await api.chat(
                query: trimmed,
                conversationID: conversationID
            )
            conversationID = result.conversationID
            messages.append(
                ChatMessage(
                    role: .assistant,
                    text: result.response,
                    evidence: result.evidence.isEmpty
                        ? result.sources
                        : result.evidence
                )
            )
        } catch {
            errorMessage = error.localizedDescription
        }

        isSending = false
    }

    func refreshHealth() async {
        guard !isCheckingHealth else { return }
        isCheckingHealth = true
        errorMessage = nil

        do {
            health = try await api.health()
        } catch {
            errorMessage = error.localizedDescription
        }

        isCheckingHealth = false
    }
}
