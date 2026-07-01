import Foundation

struct ChatMessage: Identifiable, Equatable {
    enum Role {
        case user
        case assistant
    }

    let id = UUID()
    let role: Role
    let text: String
    var evidence: [Evidence] = []
}

struct Evidence: Codable, Equatable, Identifiable {
    let provider: String?
    let text: String?
    let type: String?

    var id: String {
        [provider, type, text].compactMap { $0 }.joined(separator: ":")
    }
}

struct ChatResponse: Decodable {
    let response: String
    let sources: [Evidence]
    let evidence: [Evidence]
    let conversationID: String?

    enum CodingKeys: String, CodingKey {
        case response
        case sources
        case evidence
        case conversationID = "conversation_id"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        response = try container.decode(String.self, forKey: .response)
        sources = try container.decodeIfPresent([Evidence].self, forKey: .sources) ?? []
        evidence = try container.decodeIfPresent([Evidence].self, forKey: .evidence) ?? []
        conversationID = try container.decodeIfPresent(
            String.self,
            forKey: .conversationID
        )
    }
}

struct HealthResponse: Decodable {
    let status: String
    let buildID: String?
    let leadProvider: String?
    let providers: [String]
    let activeProvider: String?
    let activeModel: String?
    let capabilities: [String]

    enum CodingKeys: String, CodingKey {
        case status
        case providers
        case capabilities
        case buildID = "build_id"
        case leadProvider = "lead_provider"
        case activeProvider = "active_provider"
        case activeModel = "active_model"
    }
}

struct LiveKitTokenResponse: Decodable {
    let serverURL: String
    let participantToken: String
    let roomName: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case serverURL = "server_url"
        case participantToken = "participant_token"
        case roomName = "room_name"
        case expiresIn = "expires_in"
    }
}
