import FirebaseAuth
import FirebaseCore
import Foundation
import LiveKit
import Observation

@MainActor
@Observable
final class VoiceModel {
    enum State: Equatable {
        case idle
        case connecting
        case connected
        case failed(String)
    }

    private(set) var state: State = .idle
    private(set) var roomName: String?

    private let api: ConductorAPI
    private let room = Room()

    init(api: ConductorAPI = ConductorAPI()) {
        self.api = api
    }

    var isConnected: Bool {
        state == .connected
    }

    func connect() async {
        guard state != .connecting, state != .connected else { return }
        state = .connecting

        do {
            guard FirebaseApp.app() != nil else {
                throw VoiceError.firebaseNotConfigured
            }

            let user: User
            if let currentUser = Auth.auth().currentUser {
                user = currentUser
            } else {
                user = try await Auth.auth().signInAnonymously().user
            }

            let firebaseToken = try await user.getIDToken()
            let credentials = try await api.liveKitToken(
                firebaseIDToken: firebaseToken,
                displayName: "ARA iOS User"
            )

            try await room.connect(
                url: credentials.serverURL,
                token: credentials.participantToken
            )
            try await room.localParticipant.setMicrophone(enabled: true)
            roomName = credentials.roomName
            state = .connected
        } catch {
            await disconnect()
            state = .failed(error.localizedDescription)
        }
    }

    func disconnect() async {
        try? await room.localParticipant.setMicrophone(enabled: false)
        await room.disconnect()
        roomName = nil
        if case .failed = state {
            return
        }
        state = .idle
    }
}

private enum VoiceError: LocalizedError {
    case firebaseNotConfigured

    var errorDescription: String? {
        switch self {
        case .firebaseNotConfigured:
            return "Firebase configuration is not installed in this build."
        }
    }
}
