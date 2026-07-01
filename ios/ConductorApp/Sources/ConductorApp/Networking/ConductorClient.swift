import Foundation

/// Thin client for the existing Conductor Agent backend (`api/server.py`).
/// No backend changes were needed for this — /api/chat, /api/voice-chat,
/// and /health already exist and are unauthenticated by default.
public struct ConductorSource: Decodable, Identifiable {
    public var id: String { platform + title }
    public let platform: String
    public let title: String
}

public struct ConductorChatResponse: Decodable {
    public let response: String
    public let sources: [ConductorSource]
    public let audioUrl: String?

    enum CodingKeys: String, CodingKey {
        case response, sources
        case audioUrl = "audio_url"
    }
}

public struct ConductorHealth: Decodable {
    public let status: String
    public let providers: [String]
    public let apiKeysConfigured: Bool
    public let connectors: [String: Bool]
    public let voiceConfigured: Bool

    enum CodingKeys: String, CodingKey {
        case status, providers, connectors
        case apiKeysConfigured = "api_keys_configured"
        case voiceConfigured = "voice_configured"
    }
}

public final class ConductorClient {
    /// Point this at your deployed Cloud Run / Render URL for anything
    /// beyond local simulator testing against `python -m api.server`.
    public var baseURL: URL

    public init(baseURL: URL = URL(string: "http://localhost:8080")!) {
        self.baseURL = baseURL
    }

    public func health() async throws -> ConductorHealth {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appending(path: "health"))
        return try JSONDecoder().decode(ConductorHealth.self, from: data)
    }

    public func chat(query: String, platformFilter: String? = nil) async throws -> ConductorChatResponse {
        var request = URLRequest(url: baseURL.appending(path: "api/chat"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["query": query]
        if let platformFilter {
            body["platform_filter"] = platformFilter
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)
        try Self.validate(response)
        return try JSONDecoder().decode(ConductorChatResponse.self, from: data)
    }

    /// Sends a recorded voice clip (webm/m4a/wav) and gets back a
    /// transcription, text response, and a URL to synthesized audio.
    public func voiceChat(audioData: Data, filename: String = "recording.webm") async throws -> ConductorChatResponse {
        var request = URLRequest(url: baseURL.appending(path: "api/voice-chat"))
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        var httpBody = Data()
        httpBody.append("--\(boundary)\r\n".data(using: .utf8)!)
        httpBody.append(
            "Content-Disposition: form-data; name=\"audio\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!
        )
        httpBody.append("Content-Type: audio/webm\r\n\r\n".data(using: .utf8)!)
        httpBody.append(audioData)
        httpBody.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
        request.httpBody = httpBody

        let (data, response) = try await URLSession.shared.data(for: request)
        try Self.validate(response)
        return try JSONDecoder().decode(ConductorChatResponse.self, from: data)
    }

    private static func validate(_ response: URLResponse) throws {
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }
}
