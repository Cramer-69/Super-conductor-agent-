import Foundation

struct ConductorAPI {
    static let productionURL = URL(
        string: "https://conductor-agent-396823428450.us-central1.run.app"
    )!

    private let baseURL: URL
    private let session: URLSession

    init(
        baseURL: URL = Self.productionURL,
        session: URLSession = .shared
    ) {
        self.baseURL = baseURL
        self.session = session
    }

    func health() async throws -> HealthResponse {
        let url = baseURL.appending(path: "health")
        let (data, response) = try await session.data(from: url)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(HealthResponse.self, from: data)
    }

    func chat(
        query: String,
        conversationID: String?
    ) async throws -> ChatResponse {
        let url = baseURL.appending(path: "api/chat")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 90
        request.httpBody = try JSONEncoder().encode(
            ChatRequest(query: query, conversationID: conversationID)
        )

        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let response = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        guard 200..<300 ~= response.statusCode else {
            let body = String(data: data, encoding: .utf8) ?? "No response body"
            throw APIError.server(status: response.statusCode, body: body)
        }
    }
}

private struct ChatRequest: Encodable {
    let query: String
    let conversationID: String?

    enum CodingKeys: String, CodingKey {
        case query
        case conversationID = "conversation_id"
    }
}

enum APIError: LocalizedError {
    case invalidResponse
    case server(status: Int, body: String)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Conductor returned an invalid response."
        case let .server(status, body):
            return "Conductor error \(status): \(body)"
        }
    }
}
